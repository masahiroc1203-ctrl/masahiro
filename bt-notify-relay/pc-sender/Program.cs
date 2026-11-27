using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace BtNotifySender;

public class CustomReminderItem
{
    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("body")]
    public string Body { get; set; } = "";

    [JsonPropertyName("time")]
    public string Time { get; set; } = "12:00";

    [JsonPropertyName("days")]
    public List<string> Days { get; set; } = new();
}

public class AppConfig
{
    [JsonPropertyName("target_device_name")]
    public string TargetDeviceName { get; set; } = "Galaxy";

    [JsonPropertyName("enable_outlook_com")]
    public bool EnableOutlookCom { get; set; } = true;

    [JsonPropertyName("ics_sources")]
    public List<string> IcsSources { get; set; } = new();

    [JsonPropertyName("reminder_minutes_before")]
    public List<int> ReminderMinutesBefore { get; set; } = new() { 10, 5, 0 };

    [JsonPropertyName("custom_reminders")]
    public List<CustomReminderItem> CustomReminders { get; set; } = new();

    [JsonPropertyName("allowed_apps")]
    public List<string> AllowedApps { get; set; } = new();

    [JsonPropertyName("exclude_keywords")]
    public List<string> ExcludeKeywords { get; set; } = new();

    [JsonPropertyName("quiet_hours_start")]
    public string QuietHoursStart { get; set; } = "23:00";

    [JsonPropertyName("quiet_hours_end")]
    public string QuietHoursEnd { get; set; } = "07:00";
}

internal static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();

        string configPath = Path.Combine(AppContext.BaseDirectory, "config.json");
        var config = File.Exists(configPath)
            ? JsonSerializer.Deserialize<AppConfig>(File.ReadAllText(configPath)) ?? new AppConfig()
            : new AppConfig();

        using var btClient = new BluetoothClient(config.TargetDeviceName);
        using var scheduleMonitor = new ScheduleMonitor(config, (id, src, title, body) =>
            btClient.SendNotificationAsync(id, src, title, body));

        string btStatus = "初期化中";
        string schedStatus = "起動中";

        using var trayIcon = new NotifyIcon
        {
            Icon = SystemIcons.Information,
            Visible = true,
            Text = "BT Notify Relay"
        };

        void RefreshTooltip()
        {
            string text = $"BT: {btStatus} | {schedStatus}";
            trayIcon.Text = text.Length > 63 ? text[..63] : text;
        }

        btClient.StatusChanged += s => { btStatus = s; RefreshTooltip(); };
        scheduleMonitor.StatusChanged += s => { schedStatus = s; RefreshTooltip(); };

        // クイックタイマー登録用ヘルパー
        void StartQuickTimer(int minutes, string label)
        {
            var fireAt = DateTime.Now.AddMinutes(minutes);
            trayIcon.ShowBalloonTip(2000, "タイマー設定", $"{label} ({fireAt:HH:mm} にバンドへ通知)", ToolTipIcon.Info);

            _ = Task.Run(async () =>
            {
                await Task.Delay(TimeSpan.FromMinutes(minutes));
                await btClient.SendNotificationAsync(
                    $"timer-{DateTimeOffset.UtcNow.ToUnixTimeSeconds()}",
                    "PCタイマー",
                    $"{label} 経過",
                    $"{minutes}分タイマーが完了しました");
            });
        }

        var menu = new ContextMenuStrip();

        // クイックタイマー サブメニュー
        var timerMenu = new ToolStripMenuItem("クイックタイマー");
        timerMenu.DropDownItems.Add("5分後に通知", null, (_, _) => StartQuickTimer(5, "5分タイマー"));
        timerMenu.DropDownItems.Add("15分後に通知", null, (_, _) => StartQuickTimer(15, "15分タイマー"));
        timerMenu.DropDownItems.Add("25分後に通知 (ポモドーロ)", null, (_, _) => StartQuickTimer(25, "ポモドーロ25分"));
        timerMenu.DropDownItems.Add("60分後に通知", null, (_, _) => StartQuickTimer(60, "60分タイマー"));
        menu.Items.Add(timerMenu);

        menu.Items.Add("予定を今すぐ再読み込み", null, async (_, _) =>
        {
            await scheduleMonitor.ForceReloadAsync();
            trayIcon.ShowBalloonTip(2000, "BT Notify Relay", "カレンダー予定を再読み込みしました", ToolTipIcon.Info);
        });

        menu.Items.Add(new ToolStripSeparator());

        menu.Items.Add("テスト通知を送信", null, async (_, _) =>
        {
            await btClient.SendNotificationAsync(
                $"test-{DateTimeOffset.UtcNow.ToUnixTimeSeconds()}",
                "PCテスト",
                "会議リマインド (5分前)",
                "MSIXなし構成からのテスト通知です");
        });

        menu.Items.Add("config.json を開く", null, (_, _) =>
        {
            Process.Start(new ProcessStartInfo("notepad.exe", configPath) { UseShellExecute = true });
        });

        menu.Items.Add("終了", null, (_, _) => Application.Exit());
        trayIcon.ContextMenuStrip = menu;

        Application.Run();
    }
}
