namespace BtNotifySender;

/// <summary>「何分後に」「メモ」を入れてタイマーを始めるダイアログ</summary>
internal sealed class TimerDialog : Form
{
    private static readonly int[] Presets = { 3, 10, 30, 45, 90 };

    private readonly NumericUpDown _minutes;
    private readonly TextBox _memo;
    private readonly Label _preview;

    public int Minutes => (int)_minutes.Value;
    public string Memo => TimerText.NormalizeMemo(_memo.Text);

    public TimerDialog(int initialMinutes, string initialMemo)
    {
        Text = "タイマーを設定 - BT Notify Relay";
        Font = SystemFonts.MessageBoxFont ?? Font;
        AutoScaleMode = AutoScaleMode.Dpi;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        TopMost = true; // トレイから開くと、ほかのウィンドウの裏に隠れやすいため
        AutoSize = true;
        AutoSizeMode = AutoSizeMode.GrowAndShrink;
        Padding = new Padding(12);

        _minutes = new NumericUpDown
        {
            Minimum = 1,
            Maximum = TimerText.MaxMinutes,
            Value = Math.Clamp(initialMinutes, 1, TimerText.MaxMinutes),
            Width = 90,
            TextAlign = HorizontalAlignment.Right,
        };
        _minutes.ValueChanged += (_, _) => UpdatePreview();
        _minutes.KeyUp += (_, _) => UpdatePreview(); // 数字を打っている途中も表示を追従させる

        var minutesRow = new FlowLayoutPanel { AutoSize = true, WrapContents = false, Margin = new Padding(0, 0, 0, 6) };
        minutesRow.Controls.Add(_minutes);
        minutesRow.Controls.Add(new Label { Text = "分後に通知", AutoSize = true, Anchor = AnchorStyles.Left, Margin = new Padding(6, 6, 0, 0) });

        var presetRow = new FlowLayoutPanel { AutoSize = true, WrapContents = false, Margin = new Padding(0, 0, 0, 10) };
        foreach (int p in Presets)
        {
            var b = new Button { Text = TimerText.Duration(p), AutoSize = true, Margin = new Padding(0, 0, 6, 0) };
            b.Click += (_, _) => { _minutes.Value = p; _minutes.Select(); };
            presetRow.Controls.Add(b);
        }

        _memo = new TextBox
        {
            Text = initialMemo,
            MaxLength = TimerText.MaxMemoLength,
            Width = 320,
            PlaceholderText = "例: お湯が沸く、会議の準備",
            Margin = new Padding(0, 0, 0, 10),
        };

        _preview = new Label { AutoSize = true, Margin = new Padding(0, 0, 0, 12) };

        var ok = new Button { Text = "開始", DialogResult = DialogResult.OK, AutoSize = true, MinimumSize = new Size(90, 0) };
        var cancel = new Button { Text = "キャンセル", DialogResult = DialogResult.Cancel, AutoSize = true, MinimumSize = new Size(90, 0) };
        var buttons = new FlowLayoutPanel
        {
            AutoSize = true,
            FlowDirection = FlowDirection.RightToLeft,
            Dock = DockStyle.Fill,
            WrapContents = false,
        };
        buttons.Controls.Add(cancel);
        buttons.Controls.Add(ok);

        var layout = new TableLayoutPanel { AutoSize = true, ColumnCount = 1, Dock = DockStyle.Fill };
        layout.Controls.Add(new Label { Text = "何分後にバンドへ通知しますか？", AutoSize = true, Margin = new Padding(0, 0, 0, 6) });
        layout.Controls.Add(minutesRow);
        layout.Controls.Add(presetRow);
        layout.Controls.Add(new Label { Text = "メモ（バンドに表示されます。空でも OK）", AutoSize = true, Margin = new Padding(0, 0, 0, 4) });
        layout.Controls.Add(_memo);
        layout.Controls.Add(_preview);
        layout.Controls.Add(buttons);
        Controls.Add(layout);

        AcceptButton = ok;   // Enter で開始
        CancelButton = cancel; // Esc で閉じる

        Shown += (_, _) =>
        {
            Activate();
            _minutes.Select();
            _minutes.Select(0, _minutes.Text.Length);
            UpdatePreview();
        };
    }

    private void UpdatePreview()
    {
        // 入力途中の値 (Text) も反映する。範囲外や数字以外なら Value を使う
        int minutes = int.TryParse(_minutes.Text, out var typed) && typed >= 1 && typed <= TimerText.MaxMinutes
            ? typed
            : (int)_minutes.Value;
        var at = DateTime.Now.AddMinutes(minutes);
        string day = at.Date == DateTime.Today ? "" : at.Date == DateTime.Today.AddDays(1) ? "明日 " : $"{at:M/d} ";
        _preview.Text = $"→ {day}{at:HH:mm} に通知します（{TimerText.Duration(minutes)}後）";
    }
}
