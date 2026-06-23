Attribute VB_Name = "modFormLogic"
Option Explicit

' ==============================================================
' グラフ書式設定マクロ - フォームロジックモジュール
' frmChartFormatter のイベントハンドラから呼び出される
' ==============================================================

Private Const FONT_LIST   As String = "游ゴシック,游明朝,メイリオ,MS ゴシック,MS 明朝,HGゴシックE,HG明朝E,Arial,Times New Roman,Calibri,Century"
Private Const COLOR_LIST  As String = "黒,白,赤,青,緑,黄,橙,紫,灰,水"
Private Const STYLE_LIST  As String = "実線,破線,点線,一点鎖線"
Private Const WEIGHT_LIST As String = "0.25pt,0.5pt,1pt,1.5pt,2pt,2.5pt,3pt"

' --------------------------------------------------------------
' 初期化（UserForm_Initialize から呼び出し）
' --------------------------------------------------------------

Public Sub InitializeForm(frm As Object)
    Call PopulateComboBoxes(frm)
    Call SetDefaults(frm)
    Call LoadCurrentSettings(frm)
End Sub

Private Sub PopulateComboBoxes(frm As Object)
    Dim i As Integer
    Dim arr() As String

    arr = Split(FONT_LIST, ",")
    For i = 0 To UBound(arr)
        frm.Controls("cboFontName").AddItem Trim(arr(i))
    Next i

    Dim col() As String: col = Split(COLOR_LIST, ",")
    Dim sty() As String: sty = Split(STYLE_LIST, ",")
    Dim wgt() As String: wgt = Split(WEIGHT_LIST, ",")

    For i = 0 To UBound(col)
        frm.Controls("cboOuterColor").AddItem Trim(col(i))
        frm.Controls("cboPlotColor").AddItem Trim(col(i))
    Next i
    For i = 0 To UBound(sty)
        frm.Controls("cboOuterStyle").AddItem Trim(sty(i))
        frm.Controls("cboPlotStyle").AddItem Trim(sty(i))
    Next i
    For i = 0 To UBound(wgt)
        frm.Controls("cboOuterWeight").AddItem Trim(wgt(i))
        frm.Controls("cboPlotWeight").AddItem Trim(wgt(i))
    Next i

    With frm.Controls("cboXAxisPos")
        .AddItem "下": .AddItem "上": .ListIndex = 0
    End With
    With frm.Controls("cboYAxisPos")
        .AddItem "左": .AddItem "右": .ListIndex = 0
    End With
End Sub

Private Sub SetDefaults(frm As Object)
    On Error Resume Next
    frm.Controls("cboFontName").Text = "游ゴシック"
    frm.Controls("txtFontSize").Text = "11"
    frm.Controls("chkFontChartArea").Value = True
    frm.Controls("optCm").Value = True
    frm.Controls("chkOuterBorder").Value = True
    frm.Controls("chkPlotBorder").Value = True
    frm.Controls("cboOuterStyle").ListIndex = 0
    frm.Controls("cboOuterWeight").ListIndex = 2  ' 1pt
    frm.Controls("cboOuterColor").ListIndex = 0   ' 黒
    frm.Controls("cboPlotStyle").ListIndex = 0
    frm.Controls("cboPlotWeight").ListIndex = 2
    frm.Controls("cboPlotColor").ListIndex = 0
    frm.Controls("lblOuterPreview").BackColor = RGB(0, 0, 0)
    frm.Controls("lblPlotPreview").BackColor = RGB(0, 0, 0)
    On Error GoTo 0
End Sub

' --------------------------------------------------------------
' 現在のグラフ設定を読み込む（btnLoad_Click から呼び出し）
' --------------------------------------------------------------

Public Sub LoadCurrentSettings(frm As Object)
    If ActiveChart Is Nothing Then Exit Sub
    Dim cht As Chart
    Set cht = ActiveChart

    On Error Resume Next

    ' 軸タイトル
    Dim xHas As Boolean, yHas As Boolean
    xHas = cht.Axes(xlCategory).HasTitle
    yHas = cht.Axes(xlValue).HasTitle
    frm.Controls("chkXAxisTitle").Value = xHas
    If xHas Then frm.Controls("txtXAxisTitle").Text = cht.Axes(xlCategory).AxisTitle.Text
    frm.Controls("chkYAxisTitle").Value = yHas
    If yHas Then frm.Controls("txtYAxisTitle").Text = cht.Axes(xlValue).AxisTitle.Text

    ' サイズ
    Dim wCm As Double, hCm As Double
    wCm = modChartFormatter.GetCurrentChartSizeCm(cht, True)
    hCm = modChartFormatter.GetCurrentChartSizeCm(cht, False)
    If wCm > 0 Then
        frm.Controls("txtWidth").Text = Format(wCm, "0.00")
        frm.Controls("txtHeight").Text = Format(hCm, "0.00")
        frm.Controls("lblCurrentSize").Caption = _
            "現在: 幅 " & Format(wCm, "0.00") & " cm × 高さ " & Format(hCm, "0.00") & " cm"
    Else
        frm.Controls("lblCurrentSize").Caption = "グラフシート（サイズ変更不可）"
    End If

    ' フォント
    Dim fn As String, fs As Double
    fn = cht.ChartArea.Font.Name
    fs = cht.ChartArea.Font.Size
    If fn <> "" Then frm.Controls("cboFontName").Text = fn
    If fs > 0 Then frm.Controls("txtFontSize").Text = CStr(fs)
    frm.Controls("chkBold").Value = cht.ChartArea.Font.bold
    frm.Controls("chkItalic").Value = cht.ChartArea.Font.Italic

    On Error GoTo 0
    Call UpdateFontPreview(frm)
End Sub

' --------------------------------------------------------------
' 設定の適用（btnApply_Click から呼び出し）
' --------------------------------------------------------------

Public Sub ApplySettings(frm As Object)
    If ActiveChart Is Nothing Then
        MsgBox "グラフが選択されていません。" & vbCrLf & _
               "グラフをクリックしてから「適用」を押してください。", _
               vbExclamation, "グラフ書式設定"
        Exit Sub
    End If

    Dim cht As Chart
    Set cht = ActiveChart

    ' 軸ラベル
    modChartFormatter.SetAxisTitle cht, xlCategory, _
        frm.Controls("chkXAxisTitle").Value, frm.Controls("txtXAxisTitle").Text
    modChartFormatter.SetAxisTitle cht, xlValue, _
        frm.Controls("chkYAxisTitle").Value, frm.Controls("txtYAxisTitle").Text

    ' グラフサイズ
    If IsNumeric(frm.Controls("txtWidth").Text) And _
       IsNumeric(frm.Controls("txtHeight").Text) Then
        modChartFormatter.SetChartSize cht, _
            CDbl(frm.Controls("txtWidth").Text), _
            CDbl(frm.Controls("txtHeight").Text), _
            frm.Controls("optCm").Value
    End If

    ' フォント
    Dim flags As Integer: flags = 0
    If frm.Controls("chkFontChartArea").Value Then flags = flags Or 1
    If frm.Controls("chkFontTitle").Value      Then flags = flags Or 2
    If frm.Controls("chkFontAxes").Value       Then flags = flags Or 4
    If frm.Controls("chkFontLegend").Value     Then flags = flags Or 8
    Dim fSz As Double: fSz = 0
    If IsNumeric(frm.Controls("txtFontSize").Text) Then fSz = CDbl(frm.Controls("txtFontSize").Text)
    If flags > 0 Then
        modChartFormatter.SetChartFont cht, _
            frm.Controls("cboFontName").Text, fSz, _
            frm.Controls("chkBold").Value, frm.Controls("chkItalic").Value, flags
    End If

    ' 外枠
    modChartFormatter.SetChartBorder cht, True, _
        frm.Controls("chkOuterBorder").Value, _
        modChartFormatter.LineStyleNameToConst(frm.Controls("cboOuterStyle").Text), _
        modChartFormatter.WeightNameToPt(frm.Controls("cboOuterWeight").Text), _
        modChartFormatter.ColorNameToRGB(frm.Controls("cboOuterColor").Text)

    ' プロット枠
    modChartFormatter.SetChartBorder cht, False, _
        frm.Controls("chkPlotBorder").Value, _
        modChartFormatter.LineStyleNameToConst(frm.Controls("cboPlotStyle").Text), _
        modChartFormatter.WeightNameToPt(frm.Controls("cboPlotWeight").Text), _
        modChartFormatter.ColorNameToRGB(frm.Controls("cboPlotColor").Text)

    MsgBox "設定を適用しました。", vbInformation, "グラフ書式設定"
End Sub

' --------------------------------------------------------------
' フォントプレビュー更新
' --------------------------------------------------------------

Public Sub UpdateFontPreview(frm As Object)
    On Error Resume Next
    Dim lbl As Object
    Set lbl = frm.Controls("lblFontPreview")
    If frm.Controls("cboFontName").Text <> "" Then
        lbl.Font.Name = frm.Controls("cboFontName").Text
    End If
    If IsNumeric(frm.Controls("txtFontSize").Text) Then
        Dim sz As Double: sz = CDbl(frm.Controls("txtFontSize").Text)
        If sz >= 6 And sz <= 72 Then lbl.Font.Size = sz
    End If
    lbl.Font.bold = frm.Controls("chkBold").Value
    lbl.Font.Italic = frm.Controls("chkItalic").Value
    On Error GoTo 0
End Sub

' --------------------------------------------------------------
' カラープレビュー更新
' --------------------------------------------------------------

Public Sub UpdateColorPreview(frm As Object, prefix As String)
    On Error Resume Next
    frm.Controls("lbl" & prefix & "Preview").BackColor = _
        modChartFormatter.ColorNameToRGB(frm.Controls("cbo" & prefix & "Color").Text)
    On Error GoTo 0
End Sub
