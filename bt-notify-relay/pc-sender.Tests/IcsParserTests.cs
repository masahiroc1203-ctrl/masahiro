using BtNotifySender;
using Xunit;

public class IcsParserTests
{
    private static readonly TimeZoneInfo Tokyo = TimeZoneInfo.FindSystemTimeZoneById("Asia/Tokyo");
    private static readonly DateTime From = new(2026, 11, 27, 0, 0, 0);
    private static readonly DateTime To = new(2026, 11, 29, 0, 0, 0);

    private static string Calendar(params string[] events) =>
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n" + string.Join("", events) + "END:VCALENDAR\r\n";

    private static string Event(params string[] lines) =>
        "BEGIN:VEVENT\r\n" + string.Join("", lines.Select(l => l + "\r\n")) + "END:VEVENT\r\n";

    private static List<CalendarEventItem> Parse(string ics, DateTime? from = null, DateTime? to = null) =>
        IcsParser.Parse(ics, from ?? From, to ?? To, "カレンダー", Tokyo);

    [Theory]
    [InlineData("DTSTART:20261127T063000Z")]                     // UTC
    [InlineData("DTSTART;TZID=Asia/Tokyo:20261127T153000")]      // IANA
    [InlineData("DTSTART;TZID=Tokyo Standard Time:20261127T153000")] // Windows の ID (Outlook が出す形)
    [InlineData("DTSTART;TZID=America/New_York:20261127T013000")] // 別の TZ (11 月の NY は UTC-5)
    [InlineData("DTSTART:20261127T153000")]                      // TZ 指定なし = ローカル
    public void StartTime_ConvertedToLocal(string dtstart)
    {
        var events = Parse(Calendar(Event("UID:a", "SUMMARY:定例", dtstart)));
        var ev = Assert.Single(events);
        Assert.Equal(new DateTime(2026, 11, 27, 15, 30, 0), ev.StartLocal);
        Assert.Equal("定例", ev.Title);
        Assert.Equal("a", ev.UniqueId);
    }

    [Fact]
    public void FoldedLinesAndEscapes()
    {
        var ics = Calendar(Event(
            "UID:b",
            "SUMMARY:定例ミー",
            " ティング",
            "LOCATION:会議室A\\, 3F\\nビル\\\\2",
            "DTSTART:20261127T063000Z"));
        var ev = Assert.Single(Parse(ics));
        Assert.Equal("定例ミーティング", ev.Title);
        Assert.Equal("会議室A, 3F ビル\\2", ev.Location);
    }

    [Fact]
    public void AlarmSummaryDoesNotReplaceEventSummary()
    {
        var ics = Calendar(Event(
            "UID:c", "SUMMARY:本当の件名", "DTSTART:20261127T063000Z",
            "BEGIN:VALARM", "ACTION:EMAIL", "SUMMARY:アラーム", "TRIGGER:-PT10M", "END:VALARM"));
        Assert.Equal("本当の件名", Assert.Single(Parse(ics)).Title);
    }

    [Fact]
    public void SkipsAllDayCancelledAndOutOfRange()
    {
        var ics = Calendar(
            Event("UID:allday", "SUMMARY:終日", "DTSTART;VALUE=DATE:20261127"),
            Event("UID:cancel", "SUMMARY:中止", "STATUS:CANCELLED", "DTSTART:20261127T063000Z"),
            Event("UID:old", "SUMMARY:昨日", "DTSTART:20261126T063000Z"),
            Event("UID:later", "SUMMARY:来週", "DTSTART:20261204T063000Z"),
            Event("UID:ok", "SUMMARY:残る", "DTSTART:20261128T010000Z"));
        Assert.Equal(new[] { "残る" }, Parse(ics).Select(e => e.Title));
    }

    [Fact]
    public void MissingUid_UsesTitleAndTime()
    {
        var ev = Assert.Single(Parse(Calendar(Event("SUMMARY:UIDなし", "DTSTART:20261127T063000Z"))));
        Assert.Equal("UIDなし_202611271530", ev.UniqueId); // Gemini 版の {startLocal:ticks} は変な文字列になっていた
    }

    [Fact]
    public void WeeklyByDay_ExpandsIntoRange()
    {
        // 2026-11-02 (月) から毎週 月・水。範囲 11/25 (水)〜11/27 には 11/25 の回だけ
        var ics = Calendar(Event("UID:w", "SUMMARY:週次", "DTSTART;TZID=Asia/Tokyo:20261102T100000", "RRULE:FREQ=WEEKLY;BYDAY=MO,WE"));
        var events = Parse(ics, new DateTime(2026, 11, 25), new DateTime(2026, 11, 27, 23, 59, 0));
        Assert.Equal(new[] { new DateTime(2026, 11, 25, 10, 0, 0) }, events.Select(e => e.StartLocal));
    }

    [Fact]
    public void WeeklyWithoutByDay_UsesStartDay()
    {
        // 2026-11-06 (金) 開始の毎週 → 11/27 (金) が入る
        var ics = Calendar(Event("UID:w2", "SUMMARY:金曜定例", "DTSTART:20261106T053000Z", "RRULE:FREQ=WEEKLY"));
        Assert.Equal(new[] { new DateTime(2026, 11, 27, 14, 30, 0) }, Parse(ics).Select(e => e.StartLocal));
    }

    [Fact]
    public void WeeklyInterval2()
    {
        // 隔週金曜: 11/6 → 11/20 → 12/4。11/27 は無い
        var ics = Calendar(Event("UID:w3", "SUMMARY:隔週", "DTSTART:20261106T053000Z", "RRULE:FREQ=WEEKLY;INTERVAL=2"));
        Assert.Empty(Parse(ics));
    }

    [Fact]
    public void Daily_WithCountAndUntil()
    {
        var count = Calendar(Event("UID:d1", "SUMMARY:3回だけ", "DTSTART:20261123T000000Z", "RRULE:FREQ=DAILY;COUNT=3"));
        Assert.Empty(Parse(count)); // 11/23, 24, 25 で終わり

        var until = Calendar(Event("UID:d2", "SUMMARY:土曜まで", "DTSTART:20261123T000000Z", "RRULE:FREQ=DAILY;UNTIL=20261128T000000Z"));
        Assert.Equal(new[] { new DateTime(2026, 11, 27, 9, 0, 0), new DateTime(2026, 11, 28, 9, 0, 0) },
            Parse(until).Select(e => e.StartLocal));
    }

    [Fact]
    public void Daily_WithByDayFilter()
    {
        var ics = Calendar(Event("UID:d3", "SUMMARY:平日朝会", "DTSTART:20261123T000000Z", "RRULE:FREQ=DAILY;BYDAY=MO,TU,WE,TH,FR"));
        Assert.Equal(new[] { new DateTime(2026, 11, 27, 9, 0, 0) }, Parse(ics).Select(e => e.StartLocal)); // 11/28 (土) は除く
    }

    [Fact]
    public void ExDateAndRecurrenceIdOverride()
    {
        var ics = Calendar(
            Event("UID:r", "SUMMARY:毎日", "DTSTART;TZID=Asia/Tokyo:20261120T090000", "RRULE:FREQ=DAILY",
                  "EXDATE;TZID=Asia/Tokyo:20261128T090000"),
            // 11/27 の回だけ 11:00 に変更
            Event("UID:r", "SUMMARY:毎日 (変更)", "RECURRENCE-ID;TZID=Asia/Tokyo:20261127T090000",
                  "DTSTART;TZID=Asia/Tokyo:20261127T110000"));

        var events = Parse(ics, From, new DateTime(2026, 11, 29, 23, 59, 0));
        Assert.Equal(
            new[] { ("毎日 (変更)", new DateTime(2026, 11, 27, 11, 0, 0)), ("毎日", new DateTime(2026, 11, 29, 9, 0, 0)) },
            events.Select(e => (e.Title, e.StartLocal)));
    }

    [Fact]
    public void UnsupportedFrequency_KeepsFirstOccurrenceOnly()
    {
        var ics = Calendar(Event("UID:m", "SUMMARY:月次", "DTSTART:20261127T063000Z", "RRULE:FREQ=MONTHLY"));
        Assert.Single(Parse(ics));
    }

    [Fact]
    public void LfOnlyLineEndingsAndGarbage()
    {
        var ics = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:lf\nSUMMARY:LF改行\nDTSTART:20261127T063000Z\nEND:VEVENT\nこわれた行\nEND:VCALENDAR\n";
        Assert.Equal("LF改行", Assert.Single(Parse(ics)).Title);
        Assert.Empty(Parse("<html>not a calendar</html>"));
    }
}
