using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using Microsoft.Win32;

namespace BtNotifySender;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        // 二重起動するとスマホへの接続を取り合うので 1 つだけにする。
        // 「設定を反映して再起動」のときは前のプロセスが終わるまで少し待つ
        using var mutex = new Mutex(false, @"Local\BtNotifySender");
        bool acquired;
        try { acquired = mutex.WaitOne(TimeSpan.FromSeconds(5)); }
        catch (AbandonedMutexException) { acquired = true; }
        if (!acquired)
        {
            MessageBox.Show("BT Notify Relay はすでに起動しています。タスクトレイを確認してください。",
                "BT Notify Relay", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }

        try
        {
            ApplicationConfiguration.Initialize();
            Application.Run(new TrayContext());
        }
        finally
        {
            mutex.ReleaseMutex();
        }
    }
}

/// <summary>タスクトレイに常駐し、接続状態の表示とメニュー操作を受け持つ</summary>
internal sealed class TrayContext : ApplicationContext
{
    private readonly SynchronizationContext _ui;
    private readonly string _configPath;
    private readonly AppConfig _config;
    private readonly BluetoothClient _bt;
    private readonly ScheduleMonitor _schedule;
    private readonly NotifyIcon _tray;
    private readonly ToolStripMenuItem _statusItem;
    private readonly ToolStripMenuItem _scheduleItem;
    private readonly Dictionary<LinkState, Icon> _icons;

    private string _btStatus = "初期化中";
    private string _schedStatus = "予定: 読み込み中";
    private LinkState? _lastState;

    public TrayContext()
    {
        // バックグラウンドの状態通知を UI スレッドに戻すため
        SynchronizationContext.SetSynchronizationContext(new WindowsFormsSynchronizationContext());
        _ui = SynchronizationContext.Current!;

        _configPath = Path.Combine(AppContext.BaseDirectory, "config.json");
        _config = AppConfig.Load(_configPath, out var configError);

        _icons = new()
        {
            [LinkState.Connected] = MakeIcon(Color.FromArgb(0x1E, 0x9E, 0x4A)),
            [LinkState.Searching] = MakeIcon(Color.FromArgb(0xD9, 0x8E, 0x04)),
            [LinkState.Waiting] = MakeIcon(Color.FromArgb(0xD9, 0x8E, 0x04)),
            [LinkState.Error] = MakeIcon(Color.FromArgb(0xC6, 0x28, 0x28)),
        };

        _statusItem = new ToolStripMenuItem("BT: 初期化中") { Enabled = false };
        _scheduleItem = new ToolStripMenuItem(_schedStatus) { Enabled = false };

        _tray = new NotifyIcon
        {
            Icon = _icons[LinkState.Searching],
            Visible = true,
            Text = "BT Notify Relay",
            ContextMenuStrip = BuildMenu(),
        };

        _bt = new BluetoothClient(_config.TargetDeviceName);
        _bt.StatusChanged += (state, message) => _ui.Post(_ => OnLinkStatus(state, message), null);

        _schedule = new ScheduleMonitor(_config, async (id, source, title, body) =>
        {
            await _bt.SendNotificationAsync(id, source, title, body);
        });
        _schedule.StatusChanged += s => _ui.Post(_ => { _schedStatus = s; RefreshText(); }, null);

        SystemEvents.PowerModeChanged += OnPowerModeChanged;

        _bt.Start();

        if (configError is not null)
            _tray.ShowBalloonTip(8000, "BT Notify Relay", configError, ToolTipIcon.Warning);
        else
            _tray.ShowBalloonTip(3000, "BT Notify Relay", $"起動しました。接続先: 「{_config.TargetDeviceName}」を含む端末", ToolTipIcon.Info);
    }

    private ContextMenuStrip BuildMenu()
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add(_statusItem);
        menu.Items.Add(_scheduleItem);
        menu.Items.Add(new ToolStripSeparator());

        var timerMenu = new ToolStripMenuItem("クイックタイマー");
        timerMenu.DropDownItems.Add("5分後に通知", null, (_, _) => StartQuickTimer(5, "5分タイマー"));
        timerMenu.DropDownItems.Add("15分後に通知", null, (_, _) => StartQuickTimer(15, "15分タイマー"));
        timerMenu.DropDownItems.Add("25分後に通知 (ポモドーロ)", null, (_, _) => StartQuickTimer(25, "ポモドーロ25分"));
        timerMenu.DropDownItems.Add("60分後に通知", null, (_, _) => StartQuickTimer(60, "60分タイマー"));
        menu.Items.Add(timerMenu);

        menu.Items.Add("テスト通知を送信", null, async (_, _) =>
        {
            bool sent = await _bt.SendNotificationAsync(
                $"test-{DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()}",
                "PCテスト",
                "会議リマインド (5分前)",
                "PC からのテスト通知です");
            _tray.ShowBalloonTip(3000, "テスト通知",
                sent ? "スマホへ送りました。バンドに届くか確認してください"
                     : "未接続のため保留しました。つながったら送ります",
                sent ? ToolTipIcon.Info : ToolTipIcon.Warning);
        });

        menu.Items.Add("予定を今すぐ再読み込み", null, async (_, _) =>
        {
            string status = await _schedule.ForceReloadAsync();
            _tray.ShowBalloonTip(3000, "予定を再読み込み", status, ToolTipIcon.Info);
        });

        menu.Items.Add("今すぐ再接続", null, (_, _) => _bt.ReconnectNow("手動で再接続"));
        menu.Items.Add(new ToolStripSeparator());

        menu.Items.Add("config.json を開く", null, (_, _) =>
        {
            Process.Start(new ProcessStartInfo("notepad.exe", $"\"{_configPath}\"") { UseShellExecute = true });
        });
        menu.Items.Add("設定を反映して再起動", null, (_, _) =>
        {
            _tray.Visible = false;
            Application.Restart();
        });
        menu.Items.Add("終了", null, (_, _) => ExitThread());
        return menu;
    }

    private void StartQuickTimer(int minutes, string label)
    {
        var fireAt = DateTime.Now.AddMinutes(minutes);
        _tray.ShowBalloonTip(2000, "タイマー設定", $"{label} ({fireAt:HH:mm} にバンドへ通知)", ToolTipIcon.Info);

        _ = Task.Run(async () =>
        {
            await Task.Delay(TimeSpan.FromMinutes(minutes));
            await _bt.SendNotificationAsync(
                $"timer-{DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()}",
                "PCタイマー",
                $"{label} 経過",
                $"{minutes}分タイマーが完了しました ({fireAt:HH:mm})");
        });
    }

    private void OnLinkStatus(LinkState state, string message)
    {
        _btStatus = message;
        _tray.Icon = _icons[state];
        if (state == LinkState.Connected && _lastState != LinkState.Connected)
        {
            int pending = _bt.PendingCount;
            _tray.ShowBalloonTip(3000, "BT Notify Relay",
                pending > 0 ? $"{message}（保留中の {pending} 件を送ります）" : message, ToolTipIcon.Info);
        }
        _lastState = state;
        RefreshText();
    }

    private void RefreshText()
    {
        _statusItem.Text = $"BT: {_btStatus}";
        _scheduleItem.Text = _schedStatus;
        string text = $"BT Notify Relay\n{_btStatus}\n{_schedStatus}";
        try
        {
            _tray.Text = text.Length > 127 ? text[..127] : text; // .NET 8 の上限は 127 文字
        }
        catch (ArgumentOutOfRangeException)
        {
            _tray.Text = text[..Math.Min(text.Length, 63)]; // 古い上限 (63 文字) の環境向け
        }
    }

    private void OnPowerModeChanged(object? sender, PowerModeChangedEventArgs e)
    {
        // スリープ復帰後のソケットはたいてい死んでいるので、待たずにつなぎ直す
        if (e.Mode == PowerModes.Resume)
            _bt.ReconnectNow("スリープから復帰");
    }

    protected override void ExitThreadCore()
    {
        SystemEvents.PowerModeChanged -= OnPowerModeChanged;
        _tray.Visible = false;
        _schedule.Dispose();
        _bt.Dispose();
        _tray.Dispose();
        foreach (var icon in _icons.Values) icon.Dispose();
        base.ExitThreadCore();
    }

    [DllImport("user32.dll")]
    private static extern bool DestroyIcon(IntPtr hIcon);

    /// <summary>状態ごとの色の丸アイコン (緑: 接続中 / 黄: 検索・待機中 / 赤: エラー)</summary>
    private static Icon MakeIcon(Color color)
    {
        using var bmp = new Bitmap(32, 32);
        using (var g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Color.Transparent);
            using var fill = new SolidBrush(color);
            g.FillEllipse(fill, 1, 1, 30, 30);
            using var font = new Font("Segoe UI", 13f, FontStyle.Bold, GraphicsUnit.Pixel);
            var size = g.MeasureString("BT", font);
            g.DrawString("BT", font, Brushes.White, (32 - size.Width) / 2, (32 - size.Height) / 2);
        }
        IntPtr handle = bmp.GetHicon();
        try
        {
            using var temp = Icon.FromHandle(handle);
            return (Icon)temp.Clone();
        }
        finally
        {
            DestroyIcon(handle);
        }
    }
}
