using System.Globalization;

namespace BtNotifySender;

/// <summary>リマインダーの時刻計算 (副作用なし・単体テスト対象)。</summary>
public static class ReminderClock
{
    /// <summary>寝ていた・処理が遅れたなどで通知が遅れても、この時間までなら送る。それより古いものは捨てる</summary>
    public static readonly TimeSpan MaxLateness = TimeSpan.FromMinutes(2);

    public static bool TryParseTimeOfDay(string? text, out TimeSpan time)
    {
        time = default;
        if (string.IsNullOrWhiteSpace(text)) return false;
        if (!TimeSpan.TryParseExact(text.Trim(), new[] { @"h\:mm", @"hh\:mm" }, CultureInfo.InvariantCulture, out var t))
            return false;
        if (t < TimeSpan.Zero || t >= TimeSpan.FromDays(1)) return false;
        time = t;
        return true;
    }

    /// <summary>[start, end) の間なら true。日をまたぐ指定 (23:00〜07:00) にも対応。start == end や不正な値なら false</summary>
    public static bool IsQuietHours(DateTime now, string? start, string? end)
    {
        if (!TryParseTimeOfDay(start, out var s) || !TryParseTimeOfDay(end, out var e) || s == e)
            return false;

        var t = now.TimeOfDay;
        return s < e ? (t >= s && t < e) : (t >= s || t < e);
    }

    private static readonly string[] JapaneseDays = { "日", "月", "火", "水", "木", "金", "土" };

    /// <summary>days が空なら毎日。"Mon" / "monday" / "月" / "月曜" などを受け付ける</summary>
    public static bool DayMatches(IReadOnlyCollection<string> days, DayOfWeek day)
    {
        if (days.Count == 0) return true;
        string en = day.ToString()[..3];
        string ja = JapaneseDays[(int)day];
        return days.Any(d =>
        {
            var v = d.Trim();
            return v.StartsWith(en, StringComparison.OrdinalIgnoreCase) || v.StartsWith(ja, StringComparison.Ordinal);
        });
    }

    /// <summary>前回チェック from から今回 now までの間に来た時刻か (from &lt; due &lt;= now)</summary>
    public static bool IsDue(DateTime due, DateTime from, DateTime now) => due > from && due <= now;

    /// <summary>前回チェック時刻を、遅れの許容範囲に収める</summary>
    public static DateTime ClampWindowStart(DateTime lastCheck, DateTime now)
    {
        var earliest = now - MaxLateness;
        return lastCheck < earliest || lastCheck > now ? earliest : lastCheck;
    }

    /// <summary>from〜now の間に来た、自作リマインダーの発火時刻</summary>
    public static IEnumerable<DateTime> CustomReminderDueTimes(CustomReminderItem rem, DateTime from, DateTime now)
    {
        if (!TryParseTimeOfDay(rem.Time, out var tod)) yield break;
        for (var date = from.Date; date <= now.Date; date = date.AddDays(1))
        {
            var due = date + tod;
            if (DayMatches(rem.Days, date.DayOfWeek) && IsDue(due, from, now))
                yield return due;
        }
    }
}
