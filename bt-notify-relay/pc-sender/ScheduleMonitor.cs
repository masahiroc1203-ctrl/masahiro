namespace BtNotifySender;

/// <summary>
/// Outlook / ICS の予定と、自作リマインダーを監視して、時刻が来たら通知を送る。
/// </summary>
public sealed class ScheduleMonitor : IDisposable
{
    private static readonly TimeSpan CheckInterval = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan RefreshInterval = TimeSpan.FromMinutes(5);

    private readonly AppConfig _config;
    private readonly Func<string, string, string, string, Task> _onNotify;
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(10) };
    private readonly Dictionary<string, DateTime> _firedKeys = new(); // キー → 発火予定時刻 (古いものは捨てる)
    private readonly SemaphoreSlim _refreshLock = new(1, 1);
    private readonly CancellationTokenSource _cts = new();
    private volatile IReadOnlyList<CalendarEventItem> _cachedEvents = Array.Empty<CalendarEventItem>();
    private DateTime _lastFetchUtc = DateTime.MinValue;
    private DateTime _lastCheck = DateTime.Now;

    public event Action<string>? StatusChanged;
    public string LastStatus { get; private set; } = "予定: 読み込み中";

    public ScheduleMonitor(AppConfig config, Func<string, string, string, string, Task> onNotify)
    {
        _config = config;
        _onNotify = onNotify;
        _ = Task.Run(() => MonitorLoopAsync(_cts.Token));
    }

    /// <summary>予定を今すぐ読み直す。結果の状態文字列を返す</summary>
    public Task<string> ForceReloadAsync() => Task.Run(() => RefreshEventsAsync(force: true));

    private async Task MonitorLoopAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            try
            {
                var now = DateTime.Now;
                var from = ReminderClock.ClampWindowStart(_lastCheck, now);
                _lastCheck = now; // 静かな時間帯の間も進めるので、明けたときにまとめて鳴らない

                if (!ReminderClock.IsQuietHours(now, _config.QuietHoursStart, _config.QuietHoursEnd))
                {
                    await RefreshEventsAsync(force: false);
                    await CheckCalendarRemindersAsync(from, now);
                    await CheckCustomRemindersAsync(from, now);
                }
                PruneFiredKeys(now);
            }
            catch (Exception ex)
            {
                Report($"予定: 監視エラー ({ex.Message})");
            }

            try { await Task.Delay(CheckInterval, token); }
            catch (OperationCanceledException) { return; }
        }
    }

    private async Task<string> RefreshEventsAsync(bool force)
    {
        await _refreshLock.WaitAsync();
        try
        {
            if (!force && DateTime.UtcNow - _lastFetchUtc < RefreshInterval)
                return LastStatus;

            var from = DateTime.Today;
            var to = DateTime.Today.AddDays(2);
            var list = new List<CalendarEventItem>();
            var parts = new List<string>();

            if (_config.EnableOutlookCom)
            {
                list.AddRange(OutlookCalendar.Fetch(from, to, out var outlookStatus));
                parts.Add(outlookStatus);
            }

            int icsOk = 0, icsCount = 0;
            var icsErrors = new List<string>();
            foreach (var src in _config.IcsSources.Where(s => !string.IsNullOrWhiteSpace(s)))
            {
                try
                {
                    var events = IcsParser.Parse(await ReadIcsAsync(src.Trim()), from, to);
                    list.AddRange(events);
                    icsCount += events.Count;
                    icsOk++;
                }
                catch (Exception ex)
                {
                    icsErrors.Add(ex.Message);
                }
            }
            if (_config.IcsSources.Count > 0)
                parts.Add(icsErrors.Count == 0 ? $"ICS: {icsCount}件" : $"ICS: {icsCount}件 / 失敗{icsErrors.Count} ({icsErrors[0]})");

            _cachedEvents = list;
            _lastFetchUtc = DateTime.UtcNow;
            int upcoming = list.Count(e => e.StartLocal >= DateTime.Now);
            Report($"予定: これから{upcoming}件" + (parts.Count > 0 ? $" ({string.Join(" / ", parts)})" : ""));
            return LastStatus;
        }
        finally
        {
            _refreshLock.Release();
        }
    }

    private async Task<string> ReadIcsAsync(string source)
    {
        if (source.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
            source.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
        {
            return await _httpClient.GetStringAsync(source);
        }
        if (source.StartsWith("webcal://", StringComparison.OrdinalIgnoreCase))
        {
            return await _httpClient.GetStringAsync("https://" + source["webcal://".Length..]);
        }
        var path = Environment.ExpandEnvironmentVariables(source);
        if (!File.Exists(path)) throw new FileNotFoundException($"ファイルがありません: {path}");
        return await File.ReadAllTextAsync(path);
    }

    private async Task CheckCalendarRemindersAsync(DateTime from, DateTime now)
    {
        var offsets = _config.ReminderMinutesBefore.Count > 0
            ? _config.ReminderMinutesBefore.Distinct().ToList()
            : new List<int> { 5, 0 };

        foreach (var ev in _cachedEvents)
        {
            foreach (int minBefore in offsets)
            {
                var due = ev.StartLocal.AddMinutes(-minBefore);
                if (!ReminderClock.IsDue(due, from, now)) continue;

                string fireKey = $"{ev.Source}_{ev.UniqueId}_{ev.StartLocal:yyyyMMddHHmm}_{minBefore}";
                if (!_firedKeys.TryAdd(fireKey, due)) continue;

                string prefix = minBefore == 0 ? "開始時刻" : $"{minBefore}分前";
                string title = $"{ev.Title} ({prefix})";
                string body = string.IsNullOrWhiteSpace(ev.Location)
                    ? $"{ev.StartLocal:HH:mm} 開始"
                    : $"{ev.StartLocal:HH:mm} 開始 / 場所: {ev.Location}";

                await _onNotify(fireKey, ev.Source, title, body);
            }
        }
    }

    private async Task CheckCustomRemindersAsync(DateTime from, DateTime now)
    {
        for (int i = 0; i < _config.CustomReminders.Count; i++)
        {
            var rem = _config.CustomReminders[i];
            foreach (var due in ReminderClock.CustomReminderDueTimes(rem, from, now))
            {
                string fireKey = $"custom_{i}_{due:yyyyMMddHHmm}";
                if (_firedKeys.TryAdd(fireKey, due))
                    await _onNotify(fireKey, "リマインダー", rem.Title, rem.Body);
            }
        }
    }

    private void PruneFiredKeys(DateTime now)
    {
        foreach (var key in _firedKeys.Where(kv => kv.Value < now.AddDays(-1)).Select(kv => kv.Key).ToList())
            _firedKeys.Remove(key);
    }

    private void Report(string status)
    {
        LastStatus = status;
        StatusChanged?.Invoke(status);
    }

    public void Dispose()
    {
        _cts.Cancel();
        _httpClient.Dispose();
    }
}
