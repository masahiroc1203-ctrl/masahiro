using BtNotifySender;
using Microsoft.Extensions.Time.Testing;
using Xunit;

public class TimerManagerTests
{
    private static readonly DateTimeOffset Start = new(2026, 11, 27, 10, 20, 0, TimeSpan.FromHours(9));
    private static readonly TimeSpan Wait = TimeSpan.FromSeconds(5);

    private sealed class Harness : IDisposable
    {
        public readonly FakeTimeProvider Time = new(Start);
        public readonly List<ActiveTimer> Fired = new();
        public readonly SemaphoreSlim FiredSignal = new(0);
        public readonly TimerManager Timers;
        public int ChangedCount;

        public Harness()
        {
            Timers = new TimerManager(Time, t =>
            {
                lock (Fired) Fired.Add(t);
                FiredSignal.Release();
                return Task.CompletedTask;
            });
            Timers.Changed += () => Interlocked.Increment(ref ChangedCount);
        }

        /// <summary>時間を少しずつ進める (待っているループに 1 回ずつ回ってもらう)</summary>
        public void Advance(TimeSpan by)
        {
            var step = TimeSpan.FromSeconds(5);
            for (var done = TimeSpan.Zero; done < by; done += step)
            {
                Time.Advance(by - done < step ? by - done : step);
                Thread.Sleep(5);
            }
        }

        public void Dispose() => Timers.Dispose();
    }

    [Fact]
    public async Task FiresAtTheSetTimeOnce()
    {
        using var h = new Harness();
        var t = h.Timers.Start(5, "  お湯が沸く  ");
        Assert.Equal(Start.AddMinutes(5), t.FireAt);
        Assert.Equal("お湯が沸く", t.Memo);
        Assert.Single(h.Timers.Active);

        h.Advance(TimeSpan.FromSeconds(4 * 60 + 55));
        Assert.False(await h.FiredSignal.WaitAsync(TimeSpan.FromMilliseconds(200)));

        h.Advance(TimeSpan.FromSeconds(5));
        Assert.True(await h.FiredSignal.WaitAsync(Wait));
        Assert.Equal(t.Id, Assert.Single(h.Fired).Id);
        Assert.Empty(h.Timers.Active);

        h.Advance(TimeSpan.FromMinutes(10));
        Assert.False(await h.FiredSignal.WaitAsync(TimeSpan.FromMilliseconds(200)));
        Assert.Single(h.Fired);
    }

    [Fact]
    public async Task CancelledTimerNeverFires()
    {
        using var h = new Harness();
        var keep = h.Timers.Start(3, "");
        var drop = h.Timers.Start(2, "取り消す");

        Assert.True(h.Timers.Cancel(drop.Id));
        Assert.False(h.Timers.Cancel(drop.Id)); // 2 回目は何もしない
        Assert.Equal(new[] { keep.Id }, h.Timers.Active.Select(x => x.Id));

        h.Advance(TimeSpan.FromMinutes(3));
        Assert.True(await h.FiredSignal.WaitAsync(Wait));
        Assert.Equal(new[] { keep.Id }, h.Fired.Select(x => x.Id));
    }

    [Fact]
    public async Task ActiveIsSortedAndFiresInOrder()
    {
        using var h = new Harness();
        var t60 = h.Timers.Start(60, "");
        var t5 = h.Timers.Start(5, "");
        var t25 = h.Timers.Start(25, "ポモドーロ");
        Assert.Equal(new[] { t5.Id, t25.Id, t60.Id }, h.Timers.Active.Select(x => x.Id));

        h.Advance(TimeSpan.FromMinutes(60));
        for (int i = 0; i < 3; i++) Assert.True(await h.FiredSignal.WaitAsync(Wait));
        Assert.Equal(new[] { t5.Id, t25.Id, t60.Id }, h.Fired.Select(x => x.Id));
    }

    [Fact]
    public async Task WallClockJump_FiresRightAway()
    {
        // スリープ明けのように時計が一気に進んでも、次の確認で鳴る
        using var h = new Harness();
        h.Timers.Start(30, "");
        h.Time.Advance(TimeSpan.FromHours(2));
        Assert.True(await h.FiredSignal.WaitAsync(Wait));
    }

    [Fact]
    public void ChangedIsRaisedOnStartAndCancel()
    {
        using var h = new Harness();
        var t = h.Timers.Start(1, "");
        h.Timers.Cancel(t.Id);
        Assert.Equal(2, h.ChangedCount);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-5)]
    [InlineData(TimerText.MaxMinutes + 1)]
    public void RejectsOutOfRangeMinutes(int minutes)
    {
        using var h = new Harness();
        Assert.Throws<ArgumentOutOfRangeException>(() => h.Timers.Start(minutes, ""));
        Assert.Empty(h.Timers.Active);
    }

    [Fact]
    public void DisposeStopsEverything()
    {
        var h = new Harness();
        h.Timers.Start(1, "");
        h.Dispose();
        Assert.Empty(h.Timers.Active);
        Assert.Throws<ObjectDisposedException>(() => h.Timers.Start(1, ""));
        h.Advance(TimeSpan.FromMinutes(2));
        Assert.Empty(h.Fired);
    }

    [Fact]
    public void TitleAndBody()
    {
        var jst = TimeZoneInfo.FindSystemTimeZoneById("Asia/Tokyo");
        var withMemo = new ActiveTimer(1, 90, "会議の準備", Start, Start.AddMinutes(90));
        Assert.Equal("会議の準備", withMemo.Title);
        Assert.Equal("1時間30分タイマーが完了しました (10:20 に開始)", withMemo.Body(jst));

        var noMemo = new ActiveTimer(2, 25, "", Start, Start.AddMinutes(25));
        Assert.Equal("25分タイマー 経過", noMemo.Title);
    }

    [Theory]
    [InlineData(1, "1分")]
    [InlineData(59, "59分")]
    [InlineData(60, "1時間")]
    [InlineData(90, "1時間30分")]
    [InlineData(1440, "24時間")]
    public void Duration(int minutes, string expected)
    {
        Assert.Equal(expected, TimerText.Duration(minutes));
    }

    [Theory]
    [InlineData(0, "まもなく")]
    [InlineData(-10, "まもなく")]
    [InlineData(1, "1分")]
    [InlineData(60, "1分")]
    [InlineData(61, "2分")]
    [InlineData(3600, "1時間")]
    public void Remaining(int seconds, string expected)
    {
        Assert.Equal(expected, TimerText.Remaining(TimeSpan.FromSeconds(seconds)));
    }

    [Fact]
    public void NormalizeMemo_TrimsJoinsLinesAndTruncates()
    {
        Assert.Equal("1行目 2行目", TimerText.NormalizeMemo(" 1行目\r\n2行目 ".Replace("\r\n", "\n")));
        Assert.Equal("", TimerText.NormalizeMemo(null));
        Assert.Equal(TimerText.MaxMemoLength, TimerText.NormalizeMemo(new string('あ', 100)).Length);
    }
}
