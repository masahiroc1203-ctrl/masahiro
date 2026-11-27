using BtNotifySender;
using Xunit;

public class ReminderClockTests
{
    private static DateTime At(string text) => DateTime.Parse(text);

    [Theory]
    [InlineData("2026-11-27 23:30", true)]
    [InlineData("2026-11-27 23:00", true)]
    [InlineData("2026-11-28 06:59", true)]
    [InlineData("2026-11-28 07:00", false)]
    [InlineData("2026-11-27 12:00", false)]
    [InlineData("2026-11-27 22:59", false)]
    public void QuietHours_Overnight(string now, bool expected)
    {
        Assert.Equal(expected, ReminderClock.IsQuietHours(At(now), "23:00", "07:00"));
    }

    [Theory]
    [InlineData("2026-11-27 12:30", true)]
    [InlineData("2026-11-27 13:00", false)]
    [InlineData("2026-11-27 11:59", false)]
    public void QuietHours_SameDay(string now, bool expected)
    {
        Assert.Equal(expected, ReminderClock.IsQuietHours(At(now), "12:00", "13:00"));
    }

    [Theory]
    [InlineData("07:00", "07:00")]
    [InlineData("", "07:00")]
    [InlineData("25:00", "07:00")]
    [InlineData("abc", "07:00")]
    public void QuietHours_DisabledWhenEqualOrInvalid(string start, string end)
    {
        Assert.False(ReminderClock.IsQuietHours(At("2026-11-27 07:00"), start, end));
    }

    [Theory]
    [InlineData("9:05", 9, 5)]
    [InlineData("09:05", 9, 5)]
    [InlineData(" 17:15 ", 17, 15)]
    public void TryParseTimeOfDay_Accepts(string text, int h, int m)
    {
        Assert.True(ReminderClock.TryParseTimeOfDay(text, out var t));
        Assert.Equal(new TimeSpan(h, m, 0), t);
    }

    [Theory]
    [InlineData("24:00")]
    [InlineData("10:60")]
    [InlineData("10")]
    [InlineData(null)]
    public void TryParseTimeOfDay_Rejects(string? text)
    {
        Assert.False(ReminderClock.TryParseTimeOfDay(text, out _));
    }

    [Fact]
    public void DayMatches_EnglishJapaneseAndEmpty()
    {
        Assert.True(ReminderClock.DayMatches(Array.Empty<string>(), DayOfWeek.Sunday));
        Assert.True(ReminderClock.DayMatches(new[] { "Mon", "Tue" }, DayOfWeek.Monday));
        Assert.True(ReminderClock.DayMatches(new[] { "monday" }, DayOfWeek.Monday));
        Assert.True(ReminderClock.DayMatches(new[] { "月" }, DayOfWeek.Monday));
        Assert.True(ReminderClock.DayMatches(new[] { "金曜" }, DayOfWeek.Friday));
        Assert.False(ReminderClock.DayMatches(new[] { "Tue" }, DayOfWeek.Monday));
    }

    [Fact]
    public void ClampWindowStart_LimitsLateness()
    {
        var now = At("2026-11-27 10:30:00");
        Assert.Equal(now.AddSeconds(-20), ReminderClock.ClampWindowStart(now.AddSeconds(-20), now));
        Assert.Equal(now - ReminderClock.MaxLateness, ReminderClock.ClampWindowStart(now.AddHours(-3), now)); // スリープ明け
        Assert.Equal(now - ReminderClock.MaxLateness, ReminderClock.ClampWindowStart(now.AddMinutes(5), now)); // 時計が戻った
    }

    private static readonly CustomReminderItem Weekday1030 = new()
    {
        Title = "水分補給", Body = "", Time = "10:30", Days = new() { "Mon", "Tue", "Wed", "Thu", "Fri" },
    };

    [Fact]
    public void CustomReminder_FiresExactlyOnceAcrossChecks()
    {
        // 20 秒ごとのチェックを 10:29〜10:32 で回しても、発火は 1 回だけ
        var fired = new List<DateTime>();
        var last = At("2026-11-27 10:29:00"); // 金曜
        for (var now = last.AddSeconds(20); now <= At("2026-11-27 10:32:00"); now = now.AddSeconds(20))
        {
            fired.AddRange(ReminderClock.CustomReminderDueTimes(Weekday1030, ReminderClock.ClampWindowStart(last, now), now));
            last = now;
        }
        Assert.Equal(new[] { At("2026-11-27 10:30:00") }, fired);
    }

    [Fact]
    public void CustomReminder_FiresEvenIfCheckIsLate()
    {
        // 処理が詰まって 10:29:50 の次のチェックが 10:31:10 になっても、取りこぼさない
        var due = ReminderClock.CustomReminderDueTimes(Weekday1030, At("2026-11-27 10:29:50"), At("2026-11-27 10:31:10"));
        Assert.Single(due);
    }

    [Fact]
    public void CustomReminder_SkipsOtherDays()
    {
        var due = ReminderClock.CustomReminderDueTimes(Weekday1030, At("2026-11-28 10:29:50"), At("2026-11-28 10:30:10")); // 土曜
        Assert.Empty(due);
    }

    [Fact]
    public void CustomReminder_AtMidnight()
    {
        var rem = new CustomReminderItem { Title = "日付が変わりました", Time = "0:00" };
        var due = ReminderClock.CustomReminderDueTimes(rem, At("2026-11-27 23:59:50"), At("2026-11-28 00:00:10"));
        Assert.Equal(new[] { At("2026-11-28 00:00") }, due);
    }

    [Fact]
    public void CalendarReminder_WindowIsHalfOpen()
    {
        var start = At("2026-11-27 15:30");
        var due = start.AddMinutes(-5);
        Assert.False(ReminderClock.IsDue(due, due, due.AddSeconds(20)));
        Assert.True(ReminderClock.IsDue(due, due.AddSeconds(-20), due));
    }
}
