using System.Runtime.InteropServices;

namespace BtNotifySender;

/// <summary>
/// 起動中のクラシック版 Outlook から、COM で予定を読む。
/// Outlook が起動していなければ何もしない (勝手に Outlook を起動しない)。新しい Outlook には COM が無いので読めない。
/// </summary>
public static class OutlookCalendar
{
    private const int OlFolderCalendar = 9;
    private const int MaxItems = 500;

    // Marshal.GetActiveObject は .NET 5 以降に無いので、同じことを Win32 API で行う
    [DllImport("ole32.dll", CharSet = CharSet.Unicode)]
    private static extern int CLSIDFromProgID(string lpszProgID, out Guid pclsid);

    [DllImport("oleaut32.dll")]
    private static extern int GetActiveObject(ref Guid rclsid, IntPtr pvReserved,
        [MarshalAs(UnmanagedType.IUnknown)] out object? ppunk);

    public static List<CalendarEventItem> Fetch(DateTime fromLocal, DateTime toLocal, out string status)
    {
        var results = new List<CalendarEventItem>();

        if (CLSIDFromProgID("Outlook.Application", out var clsid) != 0)
        {
            status = "Outlook: クラシック版なし";
            return results;
        }
        if (GetActiveObject(ref clsid, IntPtr.Zero, out var app) != 0 || app is null)
        {
            status = "Outlook: 未起動";
            return results;
        }

        var comObjects = new List<object> { app };
        try
        {
            dynamic outlook = app;
            dynamic ns = Track(comObjects, outlook.GetNamespace("MAPI"));
            dynamic folder = Track(comObjects, ns.GetDefaultFolder(OlFolderCalendar));
            dynamic items = Track(comObjects, folder.Items);

            // 繰り返し予定を展開するには、この順番 (IncludeRecurrences → Sort → Restrict) が必要。
            // 展開後の Count は当てにならないので GetFirst / GetNext でたどる
            items.IncludeRecurrences = true;
            items.Sort("[Start]");
            // 日付の書式は Outlook (= Windows の地域設定) に合わせる
            string filter = $"[Start] >= '{fromLocal:g}' AND [Start] <= '{toLocal:g}'";
            dynamic restricted = Track(comObjects, items.Restrict(filter));

#nullable disable warnings // COM の dynamic は null 解析が効かないので、このループだけ警告を止める
            dynamic appt = restricted.GetFirst();
            for (int i = 0; appt != null && i < MaxItems; i++)
            {
                comObjects.Add(appt);
                try
                {
                    if (!(bool)appt.AllDayEvent)
                    {
                        string subject = (string?)appt.Subject is { Length: > 0 } s ? s : "(無題の予定)";
                        DateTime start = appt.Start;
                        string location = (string?)appt.Location ?? "";
                        string entryId = (string?)appt.EntryID ?? subject;
                        results.Add(new CalendarEventItem(entryId, "Outlook", subject, start, location));
                    }
                }
                catch (Exception)
                {
                    // 会議出席依頼など、予定以外のアイテムは飛ばす
                }
                appt = restricted.GetNext();
            }
#nullable restore warnings
            status = $"Outlook: {results.Count}件";
        }
        catch (Exception ex)
        {
            status = $"Outlook: 読み取り失敗 ({ex.GetType().Name})";
        }
        finally
        {
            // 参照を残すと、ユーザーが Outlook を閉じてもプロセスが残ってしまう
            for (int i = comObjects.Count - 1; i >= 0; i--)
            {
                try { Marshal.ReleaseComObject(comObjects[i]); } catch { }
            }
        }
        return results;
    }

    private static object Track(List<object> list, object obj)
    {
        list.Add(obj);
        return obj;
    }
}
