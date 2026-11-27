using System.Globalization;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;

namespace BtNotifySender;

public record CalendarEventItem(string UniqueId, string Source, string Title, DateTime StartLocal, string Location);

public class ScheduleMonitor : IDisposable
{
    private readonly AppConfig _config;
    private readonly Func<string, string, string, string, Task> _onNotify;
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(10) };
    private readonly HashSet<string> _firedKeys = new();
    private readonly CancellationTokenSource _cts = new();
    private List<CalendarEventItem> _cachedEvents = new();
    private DateTime _lastFetchUtc = DateTime.MinValue;

    public event Action<string>? StatusChanged;

    public ScheduleMonitor(AppConfig config, Func<string, string, string, string, Task> onNotify)
    {
        _config = config;
        _onNotify = onNotify;
        _ = Task.Run(() => MonitorLoopAsync(_cts.Token));
    }

    public async Task ForceReloadAsync()
    {
        _lastFetchUtc = DateTime.MinValue;
        await RefreshEventsIfNeededAsync(force: true);
    }

    private async Task MonitorLoopAsync(CancellationToken token)
    {
        while (!token.IsCancellationRequested)
        {
            try
            {
                if (!IsQuietHours())
                {
                    await RefreshEventsIfNeededAsync(force: false);
                    await CheckCalendarRemindersAsync();
                    await CheckCustomRemindersAsync();
                }
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke($"監視エラー: {ex.Message}");
            }

            await Task.Delay(TimeSpan.FromSeconds(30), token);
        }
    }

    private async Task RefreshEventsIfNeededAsync(bool force)
    {
        // カレンダーの再取得は5分間隔（ForceReload時は即時）
        if (!force && (DateTime.UtcNow - _lastFetchUtc) < TimeSpan.FromMinutes(5))
            return;

        var list = new List<CalendarEventItem>();

        if (_config.EnableOutlookCom)
        {
            list.AddRange(FetchFromClassicOutlook());
        }

        foreach (var src in _config.IcsSources.Where(s => !string.IsNullOrWhiteSpace(s)))
        {
            var icsEvents = await FetchFromIcsAsync(src.Trim());
            list.AddRange(icsEvents);
        }

        _cachedEvents = list;
        _lastFetchUtc = DateTime.UtcNow;
        StatusChanged?.Invoke($"予定監視中 ({_cachedEvents.Count}件)");
    }

    private async Task CheckCalendarRemindersAsync()
    {
        var now = DateTime.Now;
        var offsets = _config.ReminderMinutesBefore.Count > 0
            ? _config.ReminderMinutesBefore
            : new List<int> { 5, 0 };

        foreach (var ev in _cachedEvents)
        {
            double diffMinutes = (ev.StartLocal - now).TotalMinutes;

            foreach (int minBefore in offsets)
            {
                // 指定分前の前後45秒ウィンドウに入ったら発火
                if (diffMinutes <= minBefore && diffMinutes > minBefore - 0.75)
                {
                    string fireKey = $"{ev.UniqueId}_{ev.StartLocal:yyyyMMddHHmm}_{minBefore}";
                    if (_firedKeys.Add(fireKey))
                    {
                        string prefix = minBefore == 0 ? "開始時刻" : $"{minBefore}分前";
                        string title = $"{ev.Title} ({prefix})";
                        string body = string.IsNullOrWhiteSpace(ev.Location)
                            ? $"{ev.StartLocal:HH:mm} 開始"
                            : $"{ev.StartLocal:HH:mm} 開始 / 場所: {ev.Location}";

                        await _onNotify(fireKey, ev.Source, title, body);
                    }
                }
            }
        }
    }

    private async Task CheckCustomRemindersAsync()
    {
        var now = DateTime.Now;
        string todayShort = now.DayOfWeek.ToString()[..3]; // "Mon", "Tue"...
        string currentHm = now.ToString("HH:mm");

        foreach (var rem in _config.CustomReminders)
        {
            if (rem.Days.Count > 0 &&
                !rem.Days.Any(d => d.StartsWith(todayShort, StringComparison.OrdinalIgnoreCase)))
            {
                continue;
            }

            if (rem.Time == currentHm)
            {
                string fireKey = $"custom_{rem.Title}_{now:yyyyMMddHHmm}";
                if (_firedKeys.Add(fireKey))
                {
                    await _onNotify(fireKey, "リマインダー", rem.Title, rem.Body);
                }
            }
        }
    }

    // --- クラシック版 Outlook COM からの予定取得 ---
    private static List<CalendarEventItem> FetchFromClassicOutlook()
    {
        var results = new List<CalendarEventItem>();
        try
        {
            var outlookType = Type.GetTypeFromProgID("Outlook.Application");
            if (outlookType == null) return results;

            dynamic? outlookApp = null;
            try
            {
                outlookApp = Marshal.GetActiveObject("Outlook.Application");
            }
            catch
            {
                // Outlook未起動時はバックグラウンド起動を避けてスキップ
                return results;
            }

            if (outlookApp == null) return results;

            dynamic ns = outlookApp.GetNamespace("MAPI");
            dynamic calendar = ns.GetDefaultFolder(9); // 9 = olFolderCalendar
            dynamic items = calendar.Items;
            items.IncludeRecurrences = true;
            items.Sort("[Start]");

            DateTime startRange = DateTime.Today;
            DateTime endRange = DateTime.Today.AddDays(2);
            string filter = $"[Start] >= '{startRange:g}' AND [Start] <= '{endRange:g}'";
            dynamic restricted = items.Restrict(filter);

            foreach (dynamic appt in restricted)
            {
                try
                {
                    string subject = appt.Subject ?? "(無題の予定)";
                    DateTime start = appt.Start;
                    string location = appt.Location ?? "";
                    string entryId = appt.EntryID ?? subject;
                    results.Add(new CalendarEventItem(entryId, "Outlook", subject, start, location));
                }
                catch { }
            }
        }
        catch
        {
            // 新しいOutlookやCOM制限環境では無視
        }
        return results;
    }

    // --- ICS ファイル / URL パーサー ---
    private async Task<List<CalendarEventItem>> FetchFromIcsAsync(string source)
    {
        var results = new List<CalendarEventItem>();
        try
        {
            string raw = source.StartsWith("http", StringComparison.OrdinalIgnoreCase)
                ? await _httpClient.GetStringAsync(source)
                : File.Exists(source) ? await File.ReadAllTextAsync(source) : "";

            if (string.IsNullOrWhiteSpace(raw)) return results;

            // RFC5545 の行折り返し（CRLF + 空白）を解除
            string unfolded = Regex.Replace(raw, @"\r?\n[ \t]", "");
            var lines = unfolded.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);

            bool inEvent = false;
            string uid = "", summary = "", location = "", dtStartRaw = "";

            foreach (var line in lines)
            {
                if (line == "BEGIN:VEVENT")
                {
                    inEvent = true;
                    uid = ""; summary = ""; location = ""; dtStartRaw = "";
                }
                else if (line == "END:VEVENT" && inEvent)
                {
                    inEvent = false;
                    if (TryParseIcsDateTime(dtStartRaw, out var startLocal))
                    {
                        // 今日〜明日までの予定のみ保持
                        if (startLocal >= DateTime.Today && startLocal <= DateTime.Today.AddDays(2))
                        {
                            string id = string.IsNullOrEmpty(uid) ? $"{summary}_{startLocal:ticks}" : uid;
                            results.Add(new CalendarEventItem(
                                id,
                                "カレンダー",
                                string.IsNullOrEmpty(summary) ? "(無題)" : UnescapeIcsText(summary),
                                startLocal,
                                UnescapeIcsText(location)));
                        }
                    }
                }
                else if (inEvent)
                {
                    int colonIdx = line.IndexOf(':');
                    if (colonIdx <= 0) continue;

                    string prop = line[..colonIdx];
                    string val = line[(colonIdx + 1)..];

                    if (prop.StartsWith("UID")) uid = val;
                    else if (prop.StartsWith("SUMMARY")) summary = val;
                    else if (prop.StartsWith("LOCATION")) location = val;
                    else if (prop.StartsWith("DTSTART")) dtStartRaw = val;
                }
            }
        }
        catch { }
        return results;
    }

    private static bool TryParseIcsDateTime(string raw, out DateTime localTime)
    {
        localTime = default;
        if (string.IsNullOrWhiteSpace(raw)) return false;

        // UTC形式 (例: 20261127T063000Z)
        if (raw.EndsWith("Z") && DateTime.TryParseExact(
            raw, "yyyyMMdd'T'HHmmss'Z'", CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out var utc))
        {
            localTime = utc.ToLocalTime();
            return true;
        }

        // ローカル日時形式 (例: 20261127T153000)
        if (DateTime.TryParseExact(
            raw, "yyyyMMdd'T'HHmmss", CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeLocal, out var local))
        {
            localTime = local;
            return true;
        }

        return false;
    }

    private static string UnescapeIcsText(string text) =>
        text.Replace("\\n", " ").Replace("\\,", ",").Replace("\\;", ";").Replace("\\\\", "\\");

    private bool IsQuietHours()
    {
        if (!TimeSpan.TryParse(_config.QuietHoursStart, out var start) ||
            !TimeSpan.TryParse(_config.QuietHoursEnd, out var end))
            return false;

        var now = DateTime.Now.TimeOfDay;
        return start <= end ? (now >= start && now <= end) : (now >= start || now <= end);
    }

    public void Dispose()
    {
        _cts.Cancel();
        _httpClient.Dispose();
    }
}
