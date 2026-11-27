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
    private readonly ToolStripMenuItem _timerMenu;
    private readonly TimerManager _timers;
    private readonly Dictionary<LinkState, Icon> _icons;

    private string _btStatus = "初期化中";
    private string _schedStatus = "予定: 読み込み中";
    private LinkState? _lastState;
    private int _lastTimerMinutes = 10;
    private bool _timerDialogOpen;

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
        _timerMenu = new ToolStripMenuItem("タイマー");
        _timerMenu.DropDownOpening += (_, _) => RebuildTimerMenu(); // 残り時間を開くたびに更新

        _tray = new NotifyIcon
        {
            Icon = _icons[LinkState.Searching],
            Visible = true,
            Text = "BT Notify Relay",
            ContextMenuStrip = BuildMenu(),
        };

        _bt = new BluetoothClient(_config.TargetDeviceName);
        _bt.StatusChanged += (state, message) => _ui.Post(_ => OnLinkStatus(state, message), null);

        _timers = new TimerManager(TimeProvider.System, async t =>
        {
            bool sent = await _bt.SendNotificationAsync(
                $"timer-{t.Id}-{t.FireAt.ToUnixTimeSeconds()}", "PCタイマー", t.Title, t.Body(TimeZoneInfo.Local));
            _ui.Post(_ => _tray.ShowBalloonTip(4000, $"タイマー: {t.Title}",
                sent ? "バンドへ送りました" : "スマホと未接続のため保留しました（つながったら送ります）",
                sent ? ToolTipIcon.Info : ToolTipIcon.Warning), null);
        });
        _timers.Changed += () => _ui.Post(_ => RefreshText(), null);
        RebuildTimerMenu();

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

        menu.Items.Add(_timerMenu);

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
            if (!ConfirmDropTimers("再起動する")) return;
            _tray.Visible = false;
            Application.Restart();
        });
        menu.Items.Add("終了", null, (_, _) =>
        {
            if (ConfirmDropTimers("終了する")) ExitThread();
        });
        return menu;
    }

    // --- タイマー ---

    private static readonly (int Minutes, string Memo)[] QuickTimers = { (5, ""), (15, ""), (25, "ポモドーロ"), (60, "") };

    private void RebuildTimerMenu()
    {
        var items = _timerMenu.DropDownItems;
        items.Clear();
        items.Add("時間を指定して開始...", null, (_, _) => _ui.Post(_ => ShowTimerDialog(), null));
        items.Add(new ToolStripSeparator());
        foreach (var (minutes, memo) in QuickTimers)
        {
            string label = $"{TimerText.Duration(minutes)}後に通知" + (memo.Length > 0 ? $" ({memo})" : "");
            items.Add(label, null, (_, _) => StartTimer(minutes, memo));
        }

        var active = _timers.Active;
        if (active.Count == 0) return;
        items.Add(new ToolStripSeparator());
        items.Add(new ToolStripMenuItem("実行中（クリックで取り消し）") { Enabled = false });
        var now = DateTimeOffset.Now;
        foreach (var t in active)
        {
            string text = $"{FormatClock(t.FireAt)}  {t.Title}（あと{TimerText.Remaining(t.FireAt - now)}）";
            items.Add(text, null, (_, _) =>
            {
                if (_timers.Cancel(t.Id))
                    _tray.ShowBalloonTip(2000, "タイマーを取り消しました", $"{FormatClock(t.FireAt)}  {t.Title}", ToolTipIcon.Info);
            });
        }
    }

    private void ShowTimerDialog()
    {
        if (_timerDialogOpen) return;
        _timerDialogOpen = true;
        try
        {
            using var dialog = new TimerDialog(_lastTimerMinutes, "");
            if (dialog.ShowDialog() != DialogResult.OK) return;
            _lastTimerMinutes = dialog.Minutes;
            StartTimer(dialog.Minutes, dialog.Memo);
        }
        finally
        {
            _timerDialogOpen = false;
        }
    }

    private void StartTimer(int minutes, string memo)
    {
        var t = _timers.Start(minutes, memo);
        string text = $"{FormatClock(t.FireAt)} にバンドへ通知します（{TimerText.Duration(minutes)}後）";
        if (t.Memo.Length > 0) text += $"\nメモ: {t.Memo}";
        if (!_bt.IsConnected) text += "\n今はスマホと未接続です（つながったら届きます）";
        _tray.ShowBalloonTip(3000, "タイマー開始", text, ToolTipIcon.Info);
    }

    /// <summary>今日なら "10:45"、明日なら "明日 10:45"</summary>
    private static string FormatClock(DateTimeOffset at)
    {
        var local = at.ToLocalTime().DateTime;
        string day = local.Date == DateTime.Today ? "" : local.Date == DateTime.Today.AddDays(1) ? "明日 " : $"{local:M/d} ";
        return $"{day}{local:HH:mm}";
    }

    private bool ConfirmDropTimers(string action)
    {
        int count = _timers.Active.Count;
        if (count == 0) return true;
        return MessageBox.Show($"実行中のタイマーが {count} 件あります。{action}とタイマーは消えます。続けますか？",
            "BT Notify Relay", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes;
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
        var timers = _timers.Active;
        if (timers.Count > 0)
            text += $"\nタイマー: {FormatClock(timers[0].FireAt)} {timers[0].Title}" + (timers.Count > 1 ? $" ほか{timers.Count - 1}件" : "");
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
        _timers.Dispose();
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
