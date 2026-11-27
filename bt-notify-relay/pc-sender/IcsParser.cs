using System.Globalization;
using System.Text.RegularExpressions;

namespace BtNotifySender;

public record CalendarEventItem(string UniqueId, string Source, string Title, DateTime StartLocal, string Location);

/// <summary>
/// ICS (iCalendar / RFC 5545) から、指定範囲に始まる予定を取り出す。
/// 対応: 行の折り返し、TZID / UTC / 時刻指定なし、繰り返し (FREQ=DAILY / WEEKLY の INTERVAL・BYDAY・COUNT・UNTIL)、
///       EXDATE、RECURRENCE-ID (個別に変更された回)、STATUS:CANCELLED。
/// 非対応: 終日予定 (リマインド対象外として飛ばす)、MONTHLY / YEARLY の繰り返し (初回だけ扱う)。
/// </summary>
public static class IcsParser
{
    private const int MaxExpansionSteps = 20000;

    private sealed class RawEvent
    {
        public string Uid = "";
        public string Summary = "";
        public string Location = "";
        public string Status = "";
        public IcsTime? Start;
        public IcsTime? RecurrenceId;
        public string RRule = "";
        public readonly List<IcsTime> ExDates = new();
    }

    /// <summary>ICS の日時。Wall は TZ の壁時計時刻 (UTC 指定なら UTC、指定なしならローカル)</summary>
    private readonly record struct IcsTime(DateTime Wall, TimeZoneInfo Zone, bool DateOnly);

    public static List<CalendarEventItem> Parse(
        string raw, DateTime rangeStartLocal, DateTime rangeEndLocal,
        string source = "カレンダー", TimeZoneInfo? localZone = null)
    {
        var local = localZone ?? TimeZoneInfo.Local;
        var events = ReadEvents(raw, local);

        // 個別に変更・キャンセルされた回は、元の繰り返しから除く
        var overridden = new HashSet<string>(
            events.Where(e => e.RecurrenceId is not null && e.Uid != "")
                  .Select(e => OccurrenceKey(e.Uid, ToLocal(e.RecurrenceId!.Value, local))));

        var results = new List<CalendarEventItem>();
        foreach (var ev in events)
        {
            if (ev.Start is not { } start || start.DateOnly) continue; // 開始なし・終日予定は対象外
            if (ev.Status.Equals("CANCELLED", StringComparison.OrdinalIgnoreCase)) continue;

            string title = ev.Summary == "" ? "(無題)" : ev.Summary;
            IEnumerable<DateTime> starts = ev.RRule != "" && ev.RecurrenceId is null
                ? Expand(start, ev.RRule, ev.ExDates, local, rangeEndLocal)
                : new[] { ToLocal(start, local) };

            foreach (var s in starts)
            {
                if (s < rangeStartLocal || s > rangeEndLocal) continue;
                if (ev.RecurrenceId is null && ev.Uid != "" && ev.RRule != "" && overridden.Contains(OccurrenceKey(ev.Uid, s)))
                    continue;

                string id = ev.Uid != "" ? ev.Uid : $"{title}_{s:yyyyMMddHHmm}";
                results.Add(new CalendarEventItem(id, source, title, s, ev.Location));
            }
        }

        results.Sort((a, b) => a.StartLocal.CompareTo(b.StartLocal));
        return results;
    }

    private static string OccurrenceKey(string uid, DateTime local) => $"{uid}|{local:yyyyMMddHHmm}";

    private static List<RawEvent> ReadEvents(string raw, TimeZoneInfo local)
    {
        string unfolded = Regex.Replace(raw, @"\r?\n[ \t]", "");
        var lines = unfolded.Split(new[] { "\r\n", "\n", "\r" }, StringSplitOptions.None);

        var events = new List<RawEvent>();
        RawEvent? current = null;
        int nested = 0; // VEVENT 内の VALARM など。中の SUMMARY 等は予定のものではない

        foreach (var rawLine in lines)
        {
            var line = rawLine.TrimEnd();
            if (line.Length == 0) continue;

            if (line.Equals("BEGIN:VEVENT", StringComparison.OrdinalIgnoreCase))
            {
                current = new RawEvent();
                nested = 0;
                continue;
            }
            if (current is null) continue;

            if (line.Equals("END:VEVENT", StringComparison.OrdinalIgnoreCase))
            {
                events.Add(current);
                current = null;
                continue;
            }
            if (line.StartsWith("BEGIN:", StringComparison.OrdinalIgnoreCase)) { nested++; continue; }
            if (line.StartsWith("END:", StringComparison.OrdinalIgnoreCase)) { nested = Math.Max(0, nested - 1); continue; }
            if (nested > 0) continue;

            if (!TrySplitProperty(line, out var name, out var parameters, out var value)) continue;

            switch (name)
            {
                case "UID": current.Uid = value; break;
                case "SUMMARY": current.Summary = Unescape(value); break;
                case "LOCATION": current.Location = Unescape(value); break;
                case "STATUS": current.Status = value; break;
                case "RRULE": current.RRule = value; break;
                case "DTSTART": current.Start = ParseTime(value, parameters, local); break;
                case "RECURRENCE-ID": current.RecurrenceId = ParseTime(value, parameters, local); break;
                case "EXDATE":
                    foreach (var part in value.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
                        if (ParseTime(part, parameters, local) is { } ex) current.ExDates.Add(ex);
                    break;
            }
        }
        return events;
    }

    /// <summary>"NAME;P1=V1;P2=\"V:2\":VALUE" を分ける (引用符の中のコロンは区切りにしない)</summary>
    private static bool TrySplitProperty(string line, out string name, out Dictionary<string, string> parameters, out string value)
    {
        name = ""; value = "";
        parameters = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        int colon = -1;
        bool quoted = false;
        for (int i = 0; i < line.Length; i++)
        {
            if (line[i] == '"') quoted = !quoted;
            else if (line[i] == ':' && !quoted) { colon = i; break; }
        }
        if (colon <= 0) return false;

        var head = line[..colon].Split(';');
        name = head[0].Trim().ToUpperInvariant();
        foreach (var p in head.Skip(1))
        {
            int eq = p.IndexOf('=');
            if (eq > 0) parameters[p[..eq].Trim()] = p[(eq + 1)..].Trim().Trim('"');
        }
        value = line[(colon + 1)..].Trim();
        return true;
    }

    private static IcsTime? ParseTime(string value, Dictionary<string, string> parameters, TimeZoneInfo local)
    {
        bool dateOnly = parameters.TryGetValue("VALUE", out var v) && v.Equals("DATE", StringComparison.OrdinalIgnoreCase)
                        || (value.Length == 8 && value.All(char.IsDigit));
        if (dateOnly)
        {
            return DateTime.TryParseExact(value, "yyyyMMdd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var d)
                ? new IcsTime(d, local, true)
                : null;
        }

        bool utc = value.EndsWith('Z');
        var text = utc ? value[..^1] : value;
        if (!DateTime.TryParseExact(text, new[] { "yyyyMMdd'T'HHmmss", "yyyyMMdd'T'HHmm" },
                CultureInfo.InvariantCulture, DateTimeStyles.None, out var wall))
            return null;

        TimeZoneInfo zone = utc ? TimeZoneInfo.Utc
            : parameters.TryGetValue("TZID", out var tzid) && TryFindZone(tzid, out var z) ? z
            : local; // TZID が無い・見つからないときはローカル時刻として扱う
        return new IcsTime(DateTime.SpecifyKind(wall, DateTimeKind.Unspecified), zone, false);
    }

    private static bool TryFindZone(string id, out TimeZoneInfo zone)
    {
        // "/mozilla.org/20050126_1/Asia/Tokyo" のような接頭辞付きの ID にも対応
        foreach (var candidate in new[] { id, id.Contains('/') ? string.Join('/', id.Split('/').TakeLast(2)) : id })
        {
            if (TimeZoneInfo.TryFindSystemTimeZoneById(candidate, out var found))
            {
                zone = found;
                return true;
            }
        }
        zone = TimeZoneInfo.Utc;
        return false;
    }

    private static DateTime ToLocal(IcsTime t, TimeZoneInfo local)
    {
        if (t.Zone == local) return t.Wall;
        // 夏時間の切り替えで存在しない時刻 (例: 2:30) は 1 時間後として扱う
        var wall = t.Zone.IsInvalidTime(t.Wall) ? t.Wall.AddHours(1) : t.Wall;
        return TimeZoneInfo.ConvertTime(wall, t.Zone, local);
    }

    private static readonly Dictionary<string, DayOfWeek> ByDayCodes = new(StringComparer.OrdinalIgnoreCase)
    {
        ["SU"] = DayOfWeek.Sunday, ["MO"] = DayOfWeek.Monday, ["TU"] = DayOfWeek.Tuesday, ["WE"] = DayOfWeek.Wednesday,
        ["TH"] = DayOfWeek.Thursday, ["FR"] = DayOfWeek.Friday, ["SA"] = DayOfWeek.Saturday,
    };

    /// <summary>繰り返しを展開して、各回の開始 (ローカル時刻) を古い順に返す</summary>
    private static IEnumerable<DateTime> Expand(IcsTime start, string rrule, List<IcsTime> exDates, TimeZoneInfo local, DateTime rangeEndLocal)
    {
        var rule = rrule.Split(';', StringSplitOptions.RemoveEmptyEntries)
            .Select(p => p.Split('=', 2))
            .Where(kv => kv.Length == 2)
            .GroupBy(kv => kv[0].Trim().ToUpperInvariant())
            .ToDictionary(g => g.Key, g => g.First()[1].Trim());

        string freq = rule.GetValueOrDefault("FREQ", "").ToUpperInvariant();
        if (freq != "DAILY" && freq != "WEEKLY")
        {
            yield return ToLocal(start, local); // 未対応の繰り返しは初回だけ
            yield break;
        }

        int interval = int.TryParse(rule.GetValueOrDefault("INTERVAL"), out var iv) && iv > 0 ? iv : 1;
        int? count = int.TryParse(rule.GetValueOrDefault("COUNT"), out var c) && c > 0 ? c : null;
        DateTime? untilLocal = null;
        if (rule.TryGetValue("UNTIL", out var untilText))
        {
            var u = ParseTime(untilText, new Dictionary<string, string>(), start.Zone);
            if (u is { } ut)
                untilLocal = ut.DateOnly ? ut.Wall.Date.AddDays(1).AddTicks(-1) : ToLocal(ut, local);
        }

        var byDays = rule.TryGetValue("BYDAY", out var byDayText)
            ? byDayText.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(d => d.Length >= 2 ? d[^2..] : d) // "1MO" などの数字は無視
                .Where(ByDayCodes.ContainsKey)
                .Select(d => ByDayCodes[d])
                .ToHashSet()
            : new HashSet<DayOfWeek>();

        var excluded = exDates.Select(e => ToLocal(e, local).ToString("yyyyMMddHHmm")).ToHashSet();
        var timeOfDay = start.Wall.TimeOfDay;
        int produced = 0;

        IEnumerable<DateTime> Candidates()
        {
            if (freq == "DAILY")
            {
                for (int i = 0; i < MaxExpansionSteps; i++)
                    yield return start.Wall.Date.AddDays((long)i * interval) + timeOfDay;
            }
            else
            {
                // WEEKLY: 週の始まりは月曜 (WKST の既定値)
                var days = byDays.Count > 0 ? byDays : new HashSet<DayOfWeek> { start.Wall.DayOfWeek };
                int offset = ((int)start.Wall.DayOfWeek + 6) % 7;
                var weekStart = start.Wall.Date.AddDays(-offset);
                for (int w = 0; w < MaxExpansionSteps; w++)
                {
                    var ws = weekStart.AddDays((long)w * 7 * interval);
                    for (int d = 0; d < 7; d++)
                    {
                        var date = ws.AddDays(d);
                        if (days.Contains(date.DayOfWeek)) yield return date + timeOfDay;
                    }
                }
            }
        }

        int steps = 0;
        foreach (var wall in Candidates())
        {
            if (++steps > MaxExpansionSteps) yield break;
            if (wall < start.Wall) continue;
            if (freq == "DAILY" && byDays.Count > 0 && !byDays.Contains(wall.DayOfWeek)) continue;

            var occLocal = ToLocal(start with { Wall = wall }, local);
            if (untilLocal is { } until && occLocal > until) yield break;
            if (count is { } max && produced >= max) yield break;
            if (occLocal > rangeEndLocal) yield break;

            produced++; // COUNT は EXDATE で消えた回も数える (RFC 5545)
            if (!excluded.Contains(occLocal.ToString("yyyyMMddHHmm")))
                yield return occLocal;
        }
    }

    private static string Unescape(string text) =>
        Regex.Replace(text, @"\\([\\;,nN])", m => m.Groups[1].Value switch
        {
            "n" or "N" => " ",
            var other => other,
        });
}
