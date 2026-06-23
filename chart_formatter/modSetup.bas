Attribute VB_Name = "modSetup"
Option Explicit

' ==============================================================
' グラフ書式設定マクロ - セットアップモジュール
'
' 【使い方】
'   1. modChartFormatter.bas・modFormLogic.bas・modSetup.bas を
'      VBAエディタに「ファイルのインポート」でインポートする
'   2. Alt+F8 で RunSetup マクロを実行する
'      ※ 初回のみ必要（フォームが自動生成されます）
'   3. グラフを右クリック → 「グラフ書式設定」を選択
'
' 【前提条件 - 初回のみ必要】
'   Excel「ファイル」→「オプション」→「セキュリティセンター」
'   →「セキュリティセンターの設定」→「マクロの設定」→
'   「VBAプロジェクトオブジェクトモデルへのアクセスを信頼する」にチェック
' ==============================================================

Public Sub RunSetup()
    ' VBEアクセス確認
    On Error GoTo NeedTrust
    Dim testAccess As Object
    Set testAccess = ThisWorkbook.VBProject.VBComponents
    On Error GoTo 0

    Application.StatusBar = "フォームを作成しています..."
    Application.Cursor = xlWait

    Call BuildChartFormatterForm

    modChartFormatter.AddChartContextMenu

    Application.StatusBar = False
    Application.Cursor = xlDefault

    MsgBox "セットアップが完了しました！" & vbCrLf & vbCrLf & _
           "【使い方】" & vbCrLf & _
           "グラフをクリックして選択し、" & vbCrLf & _
           "右クリック → 「グラフ書式設定(F)...」を選択してください。" & vbCrLf & vbCrLf & _
           "【永続化するには】ThisWorkbook モジュールに以下を追加:" & vbCrLf & _
           "  Private Sub Workbook_Open()" & vbCrLf & _
           "      modChartFormatter.AddChartContextMenu" & vbCrLf & _
           "  End Sub", _
           vbInformation, "グラフ書式設定 セットアップ完了"
    Exit Sub

NeedTrust:
    Application.StatusBar = False
    Application.Cursor = xlDefault
    MsgBox "セットアップに失敗しました。" & vbCrLf & vbCrLf & _
           "【解決方法（1回だけ設定が必要）】" & vbCrLf & _
           "① Excelメニュー「ファイル」→「オプション」" & vbCrLf & _
           "② 「セキュリティセンター」→「セキュリティセンターの設定」" & vbCrLf & _
           "③ 「マクロの設定」タブを開く" & vbCrLf & _
           "④ 「VBAプロジェクトオブジェクトモデルへのアクセスを信頼する」にチェック" & vbCrLf & _
           "⑤ OKを押してから RunSetup を再実行", _
           vbExclamation, "セットアップエラー"
End Sub

' --------------------------------------------------------------
' フォームをプログラムで作成する
' --------------------------------------------------------------

Private Sub BuildChartFormatterForm()
    Dim vbp As Object
    Dim vbc As Object

    Set vbp = ThisWorkbook.VBProject

    ' 既存のフォームを削除
    On Error Resume Next
    Set vbc = vbp.VBComponents("frmChartFormatter")
    If Not vbc Is Nothing Then vbp.VBComponents.Remove vbc
    Set vbc = Nothing
    On Error GoTo 0

    ' 新規 UserForm を作成（vbext_ct_MSForm = 3）
    Set vbc = vbp.VBComponents.Add(3)
    vbc.Name = "frmChartFormatter"

    Dim frm As Object
    Set frm = vbc.Designer

    frm.Caption = "グラフ書式設定"
    frm.Width = 386
    frm.Height = 540
    frm.StartUpPosition = 1  ' CenterOwner

    ' MultiPage を追加
    Dim mp As Object
    Set mp = frm.Controls.Add("Forms.MultiPage.1", "MultiPage1", True)
    mp.Left = 6:  mp.Top = 6
    mp.Width = 370: mp.Height = 422

    mp.Pages(0).Caption = "軸ラベル"
    mp.Pages(1).Caption = "グラフサイズ"
    mp.Pages.Add: mp.Pages(2).Caption = "文字設定"
    mp.Pages.Add: mp.Pages(3).Caption = "枠線設定"

    ' 各タブのコントロールを追加
    Call AddAxisLabelTab(mp.Pages(0))
    Call AddSizeTab(mp.Pages(1))
    Call AddFontTab(mp.Pages(2))
    Call AddBorderTab(mp.Pages(3))

    ' 下部ボタン
    Dim b As Object
    Set b = frm.Controls.Add("Forms.CommandButton.1", "btnLoad", True)
    b.Caption = "現在の設定を読込": b.Left = 6:   b.Top = 436: b.Width = 118: b.Height = 26

    Set b = frm.Controls.Add("Forms.CommandButton.1", "btnApply", True)
    b.Caption = "適用": b.Left = 130: b.Top = 436: b.Width = 118: b.Height = 26

    Set b = frm.Controls.Add("Forms.CommandButton.1", "btnClose", True)
    b.Caption = "閉じる": b.Left = 254: b.Top = 436: b.Width = 118: b.Height = 26

    ' フォームのイベントコードを追加
    vbc.CodeModule.AddFromString GetFormEventCode()
End Sub

' --------------------------------------------------------------
' Page 0: 軸ラベル
' --------------------------------------------------------------

Private Sub AddAxisLabelTab(pg As Object)
    Dim fr As Object, c As Object

    Set fr = AddFrame(pg, "fraXAxis", "X軸（横軸）", 6, 6, 346, 136)
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkXAxisTitle", True)
    c.Caption = "X軸タイトルを表示する": c.Left = 8: c.Top = 22: c.Width = 310: c.Height = 20
    Set c = fr.Controls.Add("Forms.Label.1", "lblXT", True)
    c.Caption = "タイトル:": c.Left = 8: c.Top = 56: c.Width = 60: c.Height = 18
    Set c = fr.Controls.Add("Forms.TextBox.1", "txtXAxisTitle", True)
    c.Left = 72: c.Top = 54: c.Width = 256: c.Height = 22
    Set c = fr.Controls.Add("Forms.Label.1", "lblXP", True)
    c.Caption = "位置:": c.Left = 8: c.Top = 90: c.Width = 60: c.Height = 18
    Set c = fr.Controls.Add("Forms.ComboBox.1", "cboXAxisPos", True)
    c.Left = 72: c.Top = 88: c.Width = 100: c.Height = 20: c.Style = 2

    Set fr = AddFrame(pg, "fraYAxis", "Y軸（縦軸）", 6, 150, 346, 136)
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkYAxisTitle", True)
    c.Caption = "Y軸タイトルを表示する": c.Left = 8: c.Top = 22: c.Width = 310: c.Height = 20
    Set c = fr.Controls.Add("Forms.Label.1", "lblYT", True)
    c.Caption = "タイトル:": c.Left = 8: c.Top = 56: c.Width = 60: c.Height = 18
    Set c = fr.Controls.Add("Forms.TextBox.1", "txtYAxisTitle", True)
    c.Left = 72: c.Top = 54: c.Width = 256: c.Height = 22
    Set c = fr.Controls.Add("Forms.Label.1", "lblYP", True)
    c.Caption = "位置:": c.Left = 8: c.Top = 90: c.Width = 60: c.Height = 18
    Set c = fr.Controls.Add("Forms.ComboBox.1", "cboYAxisPos", True)
    c.Left = 72: c.Top = 88: c.Width = 100: c.Height = 20: c.Style = 2
End Sub

' --------------------------------------------------------------
' Page 1: グラフサイズ
' --------------------------------------------------------------

Private Sub AddSizeTab(pg As Object)
    Dim fr As Object, c As Object

    Set fr = AddFrame(pg, "fraSize", "サイズ設定", 6, 6, 346, 220)
    Set c = fr.Controls.Add("Forms.Label.1", "lblCurrentSize", True)
    c.Caption = "（「現在の設定を読込」を押すと現在のサイズが表示されます）"
    c.Left = 8: c.Top = 22: c.Width = 322: c.Height = 34

    Set c = fr.Controls.Add("Forms.Label.1", "lblW", True)
    c.Caption = "幅:": c.Left = 8: c.Top = 72: c.Width = 60: c.Height = 18
    Set c = fr.Controls.Add("Forms.TextBox.1", "txtWidth", True)
    c.Left = 72: c.Top = 70: c.Width = 90: c.Height = 22

    Set c = fr.Controls.Add("Forms.Label.1", "lblH", True)
    c.Caption = "高さ:": c.Left = 8: c.Top = 108: c.Width = 60: c.Height = 18
    Set c = fr.Controls.Add("Forms.TextBox.1", "txtHeight", True)
    c.Left = 72: c.Top = 106: c.Width = 90: c.Height = 22

    Set c = fr.Controls.Add("Forms.OptionButton.1", "optCm", True)
    c.Caption = "cm": c.Value = True: c.Left = 8: c.Top = 148: c.Width = 80: c.Height = 20
    Set c = fr.Controls.Add("Forms.OptionButton.1", "optPt", True)
    c.Caption = "ポイント (pt)": c.Left = 96: c.Top = 148: c.Width = 120: c.Height = 20
End Sub

' --------------------------------------------------------------
' Page 2: 文字設定
' --------------------------------------------------------------

Private Sub AddFontTab(pg As Object)
    Dim fr As Object, c As Object

    Set fr = AddFrame(pg, "fraFont", "フォント設定", 6, 6, 346, 202)
    Set c = fr.Controls.Add("Forms.Label.1", "lblFontPreviewHdr", True)
    c.Caption = "プレビュー:": c.Left = 8: c.Top = 20: c.Width = 80: c.Height = 18
    Set c = fr.Controls.Add("Forms.Label.1", "lblFontPreview", True)
    c.Caption = "Aa あいう ABC 123": c.Left = 8: c.Top = 38: c.Width = 322: c.Height = 38

    Set c = fr.Controls.Add("Forms.Label.1", "lblFN", True)
    c.Caption = "フォント名:": c.Left = 8: c.Top = 88: c.Width = 80: c.Height = 18
    Set c = fr.Controls.Add("Forms.ComboBox.1", "cboFontName", True)
    c.Left = 92: c.Top = 86: c.Width = 238: c.Height = 22

    Set c = fr.Controls.Add("Forms.Label.1", "lblFS", True)
    c.Caption = "サイズ (pt):": c.Left = 8: c.Top = 124: c.Width = 80: c.Height = 18
    Set c = fr.Controls.Add("Forms.TextBox.1", "txtFontSize", True)
    c.Left = 92: c.Top = 122: c.Width = 60: c.Height = 22

    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkBold", True)
    c.Caption = "太字 (Bold)": c.Left = 8: c.Top = 162: c.Width = 130: c.Height = 22
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkItalic", True)
    c.Caption = "斜体 (Italic)": c.Left = 148: c.Top = 162: c.Width = 130: c.Height = 22

    Set fr = AddFrame(pg, "fraTarget", "適用対象", 6, 216, 346, 110)
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkFontChartArea", True)
    c.Caption = "グラフエリア全体（推奨）": c.Value = True
    c.Left = 8: c.Top = 22: c.Width = 168: c.Height = 22
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkFontTitle", True)
    c.Caption = "グラフタイトル": c.Left = 184: c.Top = 22: c.Width = 148: c.Height = 22
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkFontAxes", True)
    c.Caption = "軸ラベル": c.Left = 8: c.Top = 54: c.Width = 168: c.Height = 22
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkFontLegend", True)
    c.Caption = "凡例": c.Left = 184: c.Top = 54: c.Width = 148: c.Height = 22
End Sub

' --------------------------------------------------------------
' Page 3: 枠線設定
' --------------------------------------------------------------

Private Sub AddBorderTab(pg As Object)
    Dim fr As Object, c As Object

    Set fr = AddFrame(pg, "fraOuterBorder", "外枠（グラフエリア）", 6, 6, 346, 170)
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkOuterBorder", True)
    c.Caption = "枠線を表示する": c.Value = True: c.Left = 8: c.Top = 22: c.Width = 200: c.Height = 22
    Call AddBorderControls(fr, "Outer", 54)

    Set fr = AddFrame(pg, "fraPlotBorder", "グラフ枠（プロットエリア）", 6, 184, 346, 170)
    Set c = fr.Controls.Add("Forms.CheckBox.1", "chkPlotBorder", True)
    c.Caption = "枠線を表示する": c.Value = True: c.Left = 8: c.Top = 22: c.Width = 200: c.Height = 22
    Call AddBorderControls(fr, "Plot", 54)
End Sub

Private Sub AddBorderControls(fr As Object, prefix As String, topY As Integer)
    Dim c As Object

    Set c = fr.Controls.Add("Forms.Label.1", "lbl" & prefix & "Style", True)
    c.Caption = "線種:": c.Left = 8: c.Top = topY: c.Width = 56: c.Height = 18
    Set c = fr.Controls.Add("Forms.ComboBox.1", "cbo" & prefix & "Style", True)
    c.Left = 68: c.Top = topY - 2: c.Width = 110: c.Height = 20: c.Style = 2

    Set c = fr.Controls.Add("Forms.Label.1", "lbl" & prefix & "Weight", True)
    c.Caption = "線幅:": c.Left = 8: c.Top = topY + 34: c.Width = 56: c.Height = 18
    Set c = fr.Controls.Add("Forms.ComboBox.1", "cbo" & prefix & "Weight", True)
    c.Left = 68: c.Top = topY + 32: c.Width = 110: c.Height = 20: c.Style = 2

    Set c = fr.Controls.Add("Forms.Label.1", "lbl" & prefix & "Color", True)
    c.Caption = "色:": c.Left = 8: c.Top = topY + 68: c.Width = 56: c.Height = 18
    Set c = fr.Controls.Add("Forms.ComboBox.1", "cbo" & prefix & "Color", True)
    c.Left = 68: c.Top = topY + 66: c.Width = 110: c.Height = 20: c.Style = 2
    Set c = fr.Controls.Add("Forms.Label.1", "lbl" & prefix & "Preview", True)
    c.BackColor = RGB(0, 0, 0): c.BackStyle = 1
    c.Left = 186: c.Top = topY + 66: c.Width = 48: c.Height = 20
End Sub

' --------------------------------------------------------------
' ヘルパー: フレームを追加して返す
' --------------------------------------------------------------

Private Function AddFrame(pg As Object, nm As String, caption As String, _
                           L As Integer, T As Integer, W As Integer, H As Integer) As Object
    Dim fr As Object
    Set fr = pg.Controls.Add("Forms.Frame.1", nm, True)
    fr.Caption = caption
    fr.Left = L: fr.Top = T: fr.Width = W: fr.Height = H
    Set AddFrame = fr
End Function

' --------------------------------------------------------------
' フォームに埋め込むイベントスタブコード
' --------------------------------------------------------------

Private Function GetFormEventCode() As String
    Dim s As String
    s = "Option Explicit" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub UserForm_Initialize()" & vbLf
    s = s & "    modFormLogic.InitializeForm Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub btnLoad_Click()" & vbLf
    s = s & "    modFormLogic.LoadCurrentSettings Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub btnApply_Click()" & vbLf
    s = s & "    modFormLogic.ApplySettings Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub btnClose_Click()" & vbLf
    s = s & "    Unload Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub cboFontName_Change()" & vbLf
    s = s & "    modFormLogic.UpdateFontPreview Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub txtFontSize_Change()" & vbLf
    s = s & "    modFormLogic.UpdateFontPreview Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub chkBold_Click()" & vbLf
    s = s & "    modFormLogic.UpdateFontPreview Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub chkItalic_Click()" & vbLf
    s = s & "    modFormLogic.UpdateFontPreview Me" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub cboOuterColor_Change()" & vbLf
    s = s & "    modFormLogic.UpdateColorPreview Me, ""Outer""" & vbLf
    s = s & "End Sub" & vbLf
    s = s & "" & vbLf
    s = s & "Private Sub cboPlotColor_Change()" & vbLf
    s = s & "    modFormLogic.UpdateColorPreview Me, ""Plot""" & vbLf
    s = s & "End Sub" & vbLf
    GetFormEventCode = s
End Function
