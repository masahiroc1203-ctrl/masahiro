namespace BtNotifySender;

public sealed record ActiveTimer(int Id, int Minutes, string Memo, DateTimeOffset StartedAt, DateTimeOffset FireAt)
{
    /// <summary>バンドに出るタイトル。メモがあればメモ、無ければ「25分タイマー 経過」</summary>
    public string Title => Memo.Length > 0 ? Memo : $"{TimerText.Duration(Minutes)}タイマー 経過";

    public string Body(TimeZoneInfo zone) =>
        $"{TimerText.Duration(Minutes)}タイマーが完了しました ({TimeZoneInfo.ConvertTime(StartedAt, zone):HH:mm} に開始)";
}

public static class TimerText
{
    public const int MaxMinutes = 24 * 60;
    public const int MaxMemoLength = 40;

    /// <summary>90 → "1時間30分"、60 → "1時間"、5 → "5分"</summary>
    public static string Duration(int minutes)
    {
        if (minutes < 60) return $"{minutes}分";
        int h = minutes / 60, m = minutes % 60;
        return m == 0 ? $"{h}時間" : $"{h}時間{m}分";
    }

    /// <summary>残り時間。端数は切り上げ ("あと1分" は 0〜60 秒)</summary>
    public static string Remaining(TimeSpan span)
    {
        if (span <= TimeSpan.Zero) return "まもなく";
        return Duration((int)Math.Ceiling(span.TotalMinutes));
    }

    public static string NormalizeMemo(string? memo)
    {
        var text = (memo ?? "").Replace('\r', ' ').Replace('\n', ' ').Trim();
        return text.Length > MaxMemoLength ? text[..MaxMemoLength] : text;
    }
}

/// <summary>
/// 好きな分数のタイマー。時刻が来たら onFire を呼ぶ。
/// PC がスリープしていても「設定した時刻」に合わせるため、長い待ちを 1 回するのではなく、
/// 短い間隔で壁時計の時刻を確かめる (スリープ中の時間を数えないタイマーがあるため)。
/// </summary>
public sealed class TimerManager : IDisposable
{
    private static readonly TimeSpan MaxStep = TimeSpan.FromSeconds(15);

    private readonly TimeProvider _time;
    private readonly Func<ActiveTimer, Task> _onFire;
    private readonly object _lock = new();
    private readonly Dictionary<int, (ActiveTimer Timer, CancellationTokenSource Cts)> _timers = new();
    private int _nextId;
    private bool _disposed;

    /// <summary>タイマーが増えた・減った (発火・取り消し) とき</summary>
    public event Action? Changed;

    public TimerManager(TimeProvider time, Func<ActiveTimer, Task> onFire)
    {
        _time = time;
        _onFire = onFire;
    }

    public ActiveTimer Start(int minutes, string? memo)
    {
        if (minutes < 1 || minutes > TimerText.MaxMinutes)
            throw new ArgumentOutOfRangeException(nameof(minutes), minutes, $"1〜{TimerText.MaxMinutes} 分で指定してください");

        var now = _time.GetUtcNow();
        var cts = new CancellationTokenSource();
        ActiveTimer timer;
        lock (_lock)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            timer = new ActiveTimer(++_nextId, minutes, TimerText.NormalizeMemo(memo), now, now.AddMinutes(minutes));
            _timers[timer.Id] = (timer, cts);
        }
        _ = RunAsync(timer, cts.Token);
        Changed?.Invoke();
        return timer;
    }

    public bool Cancel(int id)
    {
        CancellationTokenSource? cts;
        lock (_lock)
        {
            if (!_timers.Remove(id, out var entry)) return false;
            cts = entry.Cts;
        }
        cts.Cancel();
        cts.Dispose();
        Changed?.Invoke();
        return true;
    }

    /// <summary>実行中のタイマー (早く鳴る順)</summary>
    public IReadOnlyList<ActiveTimer> Active
    {
        get
        {
            lock (_lock) return _timers.Values.Select(e => e.Timer).OrderBy(t => t.FireAt).ThenBy(t => t.Id).ToList();
        }
    }

    private async Task RunAsync(ActiveTimer timer, CancellationToken token)
    {
        try
        {
            while (true)
            {
                var remaining = timer.FireAt - _time.GetUtcNow();
                if (remaining <= TimeSpan.Zero) break;
                await Task.Delay(remaining < MaxStep ? remaining : MaxStep, _time, token).ConfigureAwait(false);
            }
        }
        catch (OperationCanceledException)
        {
            return;
        }

        CancellationTokenSource? cts;
        lock (_lock)
        {
            if (!_timers.Remove(timer.Id, out var entry)) return; // 直前に取り消された
            cts = entry.Cts;
        }
        cts.Dispose();
        Changed?.Invoke();

        try
        {
            await _onFire(timer).ConfigureAwait(false);
        }
        catch (Exception)
        {
            // 送信の失敗は BluetoothClient 側で保留・再送する
        }
    }

    public void Dispose()
    {
        List<CancellationTokenSource> all;
        lock (_lock)
        {
            if (_disposed) return;
            _disposed = true;
            all = _timers.Values.Select(e => e.Cts).ToList();
            _timers.Clear();
        }
        foreach (var cts in all)
        {
            cts.Cancel();
            cts.Dispose();
        }
    }
}
