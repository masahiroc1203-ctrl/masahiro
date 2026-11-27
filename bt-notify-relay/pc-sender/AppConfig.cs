using System.Text.Json;
using System.Text.Json.Serialization;

namespace BtNotifySender;

public class CustomReminderItem
{
    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("body")]
    public string Body { get; set; } = "";

    /// <summary>"HH:mm" (例: "10:30"、"9:05" も可)</summary>
    [JsonPropertyName("time")]
    public string Time { get; set; } = "12:00";

    /// <summary>"Mon"〜"Sun" または "月"〜"日"。空なら毎日</summary>
    [JsonPropertyName("days")]
    public List<string> Days { get; set; } = new();
}

public class AppConfig
{
    /// <summary>ペアリング済みの Android 端末名に含まれる文字列 (部分一致・大文字小文字を区別しない)</summary>
    [JsonPropertyName("target_device_name")]
    public string TargetDeviceName { get; set; } = "S25";

    [JsonPropertyName("enable_outlook_com")]
    public bool EnableOutlookCom { get; set; } = true;

    /// <summary>ICS ファイルのパス、または http(s) の URL</summary>
    [JsonPropertyName("ics_sources")]
    public List<string> IcsSources { get; set; } = new();

    [JsonPropertyName("reminder_minutes_before")]
    public List<int> ReminderMinutesBefore { get; set; } = new() { 10, 5, 0 };

    [JsonPropertyName("custom_reminders")]
    public List<CustomReminderItem> CustomReminders { get; set; } = new();

    // Windows のトースト通知転送 (NotificationWatcher) 用。MSIX 化するまで未使用
    [JsonPropertyName("allowed_apps")]
    public List<string> AllowedApps { get; set; } = new();

    [JsonPropertyName("exclude_keywords")]
    public List<string> ExcludeKeywords { get; set; } = new();

    [JsonPropertyName("quiet_hours_start")]
    public string QuietHoursStart { get; set; } = "23:00";

    [JsonPropertyName("quiet_hours_end")]
    public string QuietHoursEnd { get; set; } = "07:00";

    private static readonly JsonSerializerOptions ReadOptions = new()
    {
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
    };

    private static readonly JsonSerializerOptions WriteOptions = new()
    {
        WriteIndented = true,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    /// <summary>
    /// 設定を読み込む。ファイルが無ければ既定値で作る。
    /// JSON の書き間違いがあっても落ちずに既定値で起動し、error にその内容を返す。
    /// </summary>
    public static AppConfig Load(string path, out string? error)
    {
        error = null;
        if (!File.Exists(path))
        {
            var created = new AppConfig();
            try { File.WriteAllText(path, JsonSerializer.Serialize(created, WriteOptions)); }
            catch (Exception ex) { error = $"config.json を作れませんでした: {ex.Message}"; }
            return created;
        }

        try
        {
            return Parse(File.ReadAllText(path));
        }
        catch (Exception ex) when (ex is JsonException or IOException or UnauthorizedAccessException)
        {
            error = $"config.json を読めないため既定値で起動しました: {ex.Message}";
            return new AppConfig();
        }
    }

    public static AppConfig Parse(string json) =>
        JsonSerializer.Deserialize<AppConfig>(json, ReadOptions) ?? new AppConfig();
}
