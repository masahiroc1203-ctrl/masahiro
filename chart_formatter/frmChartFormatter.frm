VERSION 5.00
Begin {C62A69F0-16DC-11CE-9E98-00AA00574A4F} frmChartFormatter
   Caption         =   "グラフ書式設定"
   ClientHeight    =   10440
   ClientLeft      =   120
   ClientTop       =   455
   ClientWidth     =   8640
   StartUpPosition =   1  'オーナーの中央
   Begin Forms.CommandButton btnClose
      Caption         =   "閉じる"
      Height          =   495
      Left            =   4680
      TabIndex        =   2
      Top             =   9840
      Width           =   1815
   End
   Begin Forms.CommandButton btnLoad
      Caption         =   "現在の設定を読込"
      Height          =   495
      Left            =   2400
      TabIndex        =   1
      Top             =   9840
      Width           =   2175
   End
   Begin Forms.CommandButton btnApply
      Caption         =   "適用"
      Height          =   495
      Left            =   120
      TabIndex        =   0
      Top             =   9840
      Width           =   2175
   End
   Begin Forms.MultiPage MultiPage1
      Height          =   9615
      Left            =   120
      TabIndex        =   3
      Top             =   120
      Width           =   8415
      Begin Forms.Page pgAxisLabel
         Caption         =   "軸ラベル"
         Begin Forms.Frame fraXAxis
            Caption         =   "X軸（横軸）"
            Height          =   2415
            Left            =   120
            Top             =   120
            Width           =   8055
            Begin Forms.ComboBox cboXAxisPos
               Height          =   330
               Left            =   2880
               TabIndex        =   3
               Top             =   1680
               Width           =   1695
            End
            Begin Forms.Label Label4
               Caption         =   "位置:"
               Height          =   255
               Left            =   1800
               Top             =   1710
               Width           =   975
            End
            Begin Forms.TextBox txtXAxisTitle
               Height          =   330
               Left            =   2880
               TabIndex        =   2
               Top             =   1200
               Width           =   4935
            End
            Begin Forms.Label Label2
               Caption         =   "タイトル:"
               Height          =   255
               Left            =   1800
               Top             =   1230
               Width           =   975
            End
            Begin Forms.CheckBox chkXAxisTitle
               Caption         =   "X軸タイトルを表示する"
               Height          =   375
               Left            =   240
               TabIndex        =   1
               Top             =   480
               Width           =   7695
               Value           =   0
            End
            Begin Forms.Label lblXNote
               Caption         =   "※ チェックを外すと軸タイトルが非表示になります"
               ForeColor       =   &H00808080&
               Height          =   255
               Left            =   240
               Top             =   960
               Width           =   7575
            End
         End
         Begin Forms.Frame fraYAxis
            Caption         =   "Y軸（縦軸）"
            Height          =   2415
            Left            =   120
            Top             =   2640
            Width           =   8055
            Begin Forms.ComboBox cboYAxisPos
               Height          =   330
               Left            =   2880
               TabIndex        =   7
               Top             =   1680
               Width           =   1695
            End
            Begin Forms.Label Label5
               Caption         =   "位置:"
               Height          =   255
               Left            =   1800
               Top             =   1710
               Width           =   975
            End
            Begin Forms.TextBox txtYAxisTitle
               Height          =   330
               Left            =   2880
               TabIndex        =   6
               Top             =   1200
               Width           =   4935
            End
            Begin Forms.Label Label3
               Caption         =   "タイトル:"
               Height          =   255
               Left            =   1800
               Top             =   1230
               Width           =   975
            End
            Begin Forms.CheckBox chkYAxisTitle
               Caption         =   "Y軸タイトルを表示する"
               Height          =   375
               Left            =   240
               TabIndex        =   5
               Top             =   480
               Width           =   7695
               Value           =   0
            End
            Begin Forms.Label lblYNote
               Caption         =   "※ チェックを外すと軸タイトルが非表示になります"
               ForeColor       =   &H00808080&
               Height          =   255
               Left            =   240
               Top             =   960
               Width           =   7575
            End
         End
      End
      Begin Forms.Page pgChartSize
         Caption         =   "グラフサイズ"
         Begin Forms.Frame fraSize
            Caption         =   "サイズ設定"
            Height          =   3135
            Left            =   120
            Top             =   120
            Width           =   8055
            Begin Forms.OptionButton optPt
               Caption         =   "ポイント (pt)"
               Height          =   375
               Left            =   4680
               TabIndex        =   5
               Top             =   2520
               Width           =   1815
            End
            Begin Forms.OptionButton optCm
               Caption         =   "センチメートル (cm)"
               Height          =   375
               Left            =   480
               TabIndex        =   4
               Top             =   2520
               Value           =   -1
               Width           =   4095
            End
            Begin Forms.TextBox txtHeight
               Height          =   375
               Left            =   2880
               TabIndex        =   3
               Top             =   1800
               Width           =   1815
            End
            Begin Forms.Label Label7
               Caption         =   "高さ:"
               Height          =   330
               Left            =   480
               Top             =   1830
               Width           =   2175
            End
            Begin Forms.TextBox txtWidth
               Height          =   375
               Left            =   2880
               TabIndex        =   2
               Top             =   1200
               Width           =   1815
            End
            Begin Forms.Label Label6
               Caption         =   "幅:"
               Height          =   330
               Left            =   480
               Top             =   1230
               Width           =   2175
            End
            Begin Forms.Label lblCurrentSize
               Caption         =   "現在のサイズ: (グラフを選択して「現在の設定を読込」を押してください)"
               ForeColor       =   &H00808080&
               Height          =   495
               Left            =   480
               Top             =   480
               Width           =   7455
            End
         End
      End
      Begin Forms.Page pgFont
         Caption         =   "文字設定"
         Begin Forms.Frame fraFontTarget
            Caption         =   "適用対象"
            Height          =   2175
            Left            =   120
            Top             =   3600
            Width           =   8055
            Begin Forms.CheckBox chkFontLegend
               Caption         =   "凡例"
               Height          =   375
               Left            =   4200
               TabIndex        =   12
               Top             =   1320
               Width           =   3735
               Value           =   0
            End
            Begin Forms.CheckBox chkFontAxes
               Caption         =   "軸ラベル（軸タイトル・目盛り）"
               Height          =   375
               Left            =   240
               TabIndex        =   11
               Top             =   1320
               Width           =   3855
               Value           =   0
            End
            Begin Forms.CheckBox chkFontTitle
               Caption         =   "グラフタイトル"
               Height          =   375
               Left            =   4200
               TabIndex        =   10
               Top             =   840
               Width           =   3735
               Value           =   0
            End
            Begin Forms.CheckBox chkFontChartArea
               Caption         =   "グラフエリア全体（推奨）"
               Height          =   375
               Left            =   240
               TabIndex        =   9
               Top             =   840
               Width           =   3855
               Value           =   -1
            End
            Begin Forms.Label lblTargetNote
               Caption         =   "「グラフエリア全体」はすべての文字に一括適用します"
               ForeColor       =   &H00808080&
               Height          =   375
               Left            =   240
               Top             =   360
               Width           =   7695
            End
         End
         Begin Forms.Frame fraFont
            Caption         =   "フォント設定"
            Height          =   3495
            Left            =   120
            Top             =   0
            Width           =   8055
            Begin Forms.CheckBox chkItalic
               Caption         =   "斜体 (Italic)"
               Height          =   375
               Left            =   4200
               TabIndex        =   8
               Top             =   2760
               Width           =   3735
               Value           =   0
            End
            Begin Forms.CheckBox chkBold
               Caption         =   "太字 (Bold)"
               Height          =   375
               Left            =   240
               TabIndex        =   7
               Top             =   2760
               Width           =   3855
               Value           =   0
            End
            Begin Forms.TextBox txtFontSize
               Height          =   375
               Left            =   2880
               TabIndex        =   6
               Top             =   2160
               Width           =   975
            End
            Begin Forms.Label Label9
               Caption         =   "フォントサイズ (pt):"
               Height          =   330
               Left            =   240
               Top             =   2190
               Width           =   2535
            End
            Begin Forms.ComboBox cboFontName
               Height          =   375
               Left            =   2880
               TabIndex        =   5
               Top             =   1560
               Width           =   4935
            End
            Begin Forms.Label Label8
               Caption         =   "フォント名:"
               Height          =   330
               Left            =   240
               Top             =   1590
               Width           =   2535
            End
            Begin Forms.Label lblFontPreview
               Caption         =   "Aa Bb Cc あいう アイウ 123"
               Font            =   "MS ゴシック"
               Height          =   615
               Left            =   240
               Top             =   720
               Width           =   7695
            End
            Begin Forms.Label lblFontPreviewHdr
               Caption         =   "プレビュー:"
               Height          =   255
               Left            =   240
               Top             =   480
               Width           =   2535
            End
         End
      End
      Begin Forms.Page pgBorder
         Caption         =   "枠線設定"
         Begin Forms.Frame fraPlotBorder
            Caption         =   "グラフ枠（プロットエリア）"
            Height          =   3375
            Left            =   120
            Top             =   4200
            Width           =   8055
            Begin Forms.Label lblPlotColorPreview
               BackColor       =   &H00000000&
               BackStyle       =   1
               Height          =   255
               Left            =   6480
               Top             =   2760
               Width           =   1335
            End
            Begin Forms.ComboBox cboPlotColor
               Height          =   330
               Left            =   2880
               TabIndex        =   22
               Top             =   2760
               Width           =   3495
            End
            Begin Forms.Label Label18
               Caption         =   "色:"
               Height          =   255
               Left            =   240
               Top             =   2790
               Width           =   2535
            End
            Begin Forms.ComboBox cboPlotWeight
               Height          =   330
               Left            =   2880
               TabIndex        =   21
               Top             =   2280
               Width           =   3495
            End
            Begin Forms.Label Label17
               Caption         =   "線幅:"
               Height          =   255
               Left            =   240
               Top             =   2310
               Width           =   2535
            End
            Begin Forms.ComboBox cboPlotStyle
               Height          =   330
               Left            =   2880
               TabIndex        =   20
               Top             =   1800
               Width           =   3495
            End
            Begin Forms.Label Label16
               Caption         =   "線種:"
               Height          =   255
               Left            =   240
               Top             =   1830
               Width           =   2535
            End
            Begin Forms.CheckBox chkPlotBorder
               Caption         =   "プロットエリアに枠線を表示する"
               Height          =   375
               Left            =   240
               TabIndex        =   19
               Top             =   960
               Width           =   7575
               Value           =   -1
            End
            Begin Forms.Label lblPlotNote
               Caption         =   "※ チェックを外すと枠線が非表示になります"
               ForeColor       =   &H00808080&
               Height          =   375
               Left            =   240
               Top             =   480
               Width           =   7575
            End
         End
         Begin Forms.Frame fraOuterBorder
            Caption         =   "外枠（グラフエリア）"
            Height          =   4095
            Left            =   120
            Top             =   0
            Width           =   8055
            Begin Forms.Label lblOuterColorPreview
               BackColor       =   &H00000000&
               BackStyle       =   1
               Height          =   255
               Left            =   6480
               Top             =   3480
               Width           =   1335
            End
            Begin Forms.ComboBox cboOuterColor
               Height          =   330
               Left            =   2880
               TabIndex        =   17
               Top             =   3480
               Width           =   3495
            End
            Begin Forms.Label Label15
               Caption         =   "色:"
               Height          =   255
               Left            =   240
               Top             =   3510
               Width           =   2535
            End
            Begin Forms.ComboBox cboOuterWeight
               Height          =   330
               Left            =   2880
               TabIndex        =   16
               Top             =   2880
               Width           =   3495
            End
            Begin Forms.Label Label14
               Caption         =   "線幅:"
               Height          =   255
               Left            =   240
               Top             =   2910
               Width           =   2535
            End
            Begin Forms.ComboBox cboOuterStyle
               Height          =   330
               Left            =   2880
               TabIndex        =   15
               Top             =   2280
               Width           =   3495
            End
            Begin Forms.Label Label13
               Caption         =   "線種:"
               Height          =   255
               Left            =   240
               Top             =   2310
               Width           =   2535
            End
            Begin Forms.CheckBox chkOuterBorder
               Caption         =   "グラフエリアに枠線を表示する"
               Height          =   375
               Left            =   240
               TabIndex        =   14
               Top             =   1560
               Width           =   7575
               Value           =   -1
            End
            Begin Forms.Label lblOuterNote2
               Caption         =   "※ チェックを外すと枠線が非表示になります"
               ForeColor       =   &H00808080&
               Height          =   375
               Left            =   240
               Top             =   1200
               Width           =   7575
            End
            Begin Forms.Label lblOuterNote1
               Caption         =   "グラフ全体を囲む外側の枠線を設定します"
               Height          =   375
               Left            =   240
               Top             =   720
               Width           =   7575
            End
         End
      End
   End
End
Attribute VB_Name = "frmChartFormatter"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Explicit

' ---------------------------------------------------------------
' 定数
' ---------------------------------------------------------------
Private Const FONT_NAMES As String = "游ゴシック,游明朝,メイリオ,MS ゴシック,MS 明朝,ＭＳ ゴシック,ＭＳ 明朝,HGゴシックE,HG明朝E,Arial,Times New Roman,Calibri,Century,Century Gothic"
Private Const COLOR_NAMES As String = "黒,白,赤,青,緑,黄,オレンジ,紫,グレー,水色"
Private Const LINE_STYLES As String = "実線,破線,点線,一点鎖線"
Private Const BORDER_WEIGHTS As String = "0.25pt,0.5pt,1pt,1.5pt,2pt,2.5pt,3pt"

' ---------------------------------------------------------------
' 初期化
' ---------------------------------------------------------------
Private Sub UserForm_Initialize()
    Call InitializeComboBoxes
    Call InitializeDefaults
    Call LoadCurrentSettings
End Sub

Private Sub InitializeComboBoxes()
    Dim i As Integer
    Dim items() As String

    ' フォント名
    items = Split(FONT_NAMES, ",")
    For i = 0 To UBound(items)
        cboFontName.AddItem Trim(items(i))
    Next i

    ' 色コンボ
    items = Split(COLOR_NAMES, ",")
    For i = 0 To UBound(items)
        cboOuterColor.AddItem Trim(items(i))
        cboPlotColor.AddItem Trim(items(i))
    Next i

    ' 線種コンボ
    items = Split(LINE_STYLES, ",")
    For i = 0 To UBound(items)
        cboOuterStyle.AddItem Trim(items(i))
        cboPlotStyle.AddItem Trim(items(i))
    Next i

    ' 線幅コンボ
    items = Split(BORDER_WEIGHTS, ",")
    For i = 0 To UBound(items)
        cboOuterWeight.AddItem Trim(items(i))
        cboPlotWeight.AddItem Trim(items(i))
    Next i

    ' 軸位置（X軸）
    cboXAxisPos.AddItem "下"
    cboXAxisPos.AddItem "上"
    cboXAxisPos.ListIndex = 0

    ' 軸位置（Y軸）
    cboYAxisPos.AddItem "左"
    cboYAxisPos.AddItem "右"
    cboYAxisPos.ListIndex = 0
End Sub

Private Sub InitializeDefaults()
    ' フォントデフォルト
    cboFontName.Text = "游ゴシック"
    txtFontSize.Text = "11"
    chkBold.Value = False
    chkItalic.Value = False
    chkFontChartArea.Value = True

    ' 単位デフォルト
    optCm.Value = True

    ' 枠線デフォルト
    cboOuterStyle.ListIndex = 0  ' 実線
    cboOuterWeight.ListIndex = 2 ' 1pt
    cboOuterColor.ListIndex = 0  ' 黒
    lblOuterColorPreview.BackColor = RGB(0, 0, 0)

    cboPlotStyle.ListIndex = 0   ' 実線
    cboPlotWeight.ListIndex = 2  ' 1pt
    cboPlotColor.ListIndex = 0   ' 黒
    lblPlotColorPreview.BackColor = RGB(0, 0, 0)
End Sub

Private Sub LoadCurrentSettings()
    If ActiveChart Is Nothing Then Exit Sub

    Dim cht As Chart
    Set cht = ActiveChart

    ' 軸タイトル読込
    On Error Resume Next
    Dim xHas As Boolean, yHas As Boolean
    xHas = cht.Axes(xlCategory).HasTitle
    yHas = cht.Axes(xlValue).HasTitle

    chkXAxisTitle.Value = xHas
    If xHas Then txtXAxisTitle.Text = cht.Axes(xlCategory).AxisTitle.Text

    chkYAxisTitle.Value = yHas
    If yHas Then txtYAxisTitle.Text = cht.Axes(xlValue).AxisTitle.Text

    ' サイズ読込
    Dim wCm As Double, hCm As Double
    wCm = modChartFormatter.GetCurrentChartSizeCm(cht, True)
    hCm = modChartFormatter.GetCurrentChartSizeCm(cht, False)
    If wCm > 0 Then
        txtWidth.Text = Format(wCm, "0.00")
        txtHeight.Text = Format(hCm, "0.00")
        lblCurrentSize.Caption = "現在のサイズ: 幅 " & Format(wCm, "0.00") & _
                                  " cm × 高さ " & Format(hCm, "0.00") & " cm"
    Else
        lblCurrentSize.Caption = "現在のサイズ: グラフシート（サイズ変更不可）"
    End If

    ' フォント読込
    Dim fName As String, fSize As Double
    fName = cht.ChartArea.Font.Name
    fSize = cht.ChartArea.Font.Size
    If fName <> "" Then cboFontName.Text = fName
    If fSize > 0 Then txtFontSize.Text = CStr(fSize)
    chkBold.Value = cht.ChartArea.Font.bold
    chkItalic.Value = cht.ChartArea.Font.Italic

    On Error GoTo 0
    Call UpdateFontPreview
End Sub

' ---------------------------------------------------------------
' ボタンイベント
' ---------------------------------------------------------------

Private Sub btnLoad_Click()
    Call LoadCurrentSettings
End Sub

Private Sub btnApply_Click()
    If ActiveChart Is Nothing Then
        MsgBox "グラフが選択されていません。グラフをクリックしてから「適用」を押してください。", _
               vbExclamation, "グラフ書式設定"
        Exit Sub
    End If

    Dim cht As Chart
    Set cht = ActiveChart

    ' --- 軸ラベル ---
    Call modChartFormatter.SetAxisTitle(cht, xlCategory, _
         chkXAxisTitle.Value, txtXAxisTitle.Text)
    Call modChartFormatter.SetAxisTitle(cht, xlValue, _
         chkYAxisTitle.Value, txtYAxisTitle.Text)

    ' --- グラフサイズ ---
    Dim w As Double, h As Double
    If IsNumeric(txtWidth.Text) And IsNumeric(txtHeight.Text) Then
        w = CDbl(txtWidth.Text)
        h = CDbl(txtHeight.Text)
        Call modChartFormatter.SetChartSize(cht, w, h, optCm.Value)
    End If

    ' --- フォント ---
    Dim targetFlags As Integer
    targetFlags = 0
    If chkFontChartArea.Value Then targetFlags = targetFlags Or 1
    If chkFontTitle.Value Then targetFlags = targetFlags Or 2
    If chkFontAxes.Value Then targetFlags = targetFlags Or 4
    If chkFontLegend.Value Then targetFlags = targetFlags Or 8

    Dim fSize As Double
    fSize = 0
    If IsNumeric(txtFontSize.Text) Then fSize = CDbl(txtFontSize.Text)

    If targetFlags > 0 Then
        Call modChartFormatter.SetChartFont(cht, cboFontName.Text, fSize, _
             chkBold.Value, chkItalic.Value, targetFlags)
    End If

    ' --- 外枠 ---
    Call modChartFormatter.SetChartBorder(cht, True, _
         chkOuterBorder.Value, _
         modChartFormatter.LineStyleNameToConst(cboOuterStyle.Text), _
         modChartFormatter.WeightNameToPt(cboOuterWeight.Text), _
         modChartFormatter.ColorNameToRGB(cboOuterColor.Text))

    ' --- プロット枠 ---
    Call modChartFormatter.SetChartBorder(cht, False, _
         chkPlotBorder.Value, _
         modChartFormatter.LineStyleNameToConst(cboPlotStyle.Text), _
         modChartFormatter.WeightNameToPt(cboPlotWeight.Text), _
         modChartFormatter.ColorNameToRGB(cboPlotColor.Text))

    MsgBox "設定を適用しました。", vbInformation, "グラフ書式設定"
End Sub

Private Sub btnClose_Click()
    Unload Me
End Sub

' ---------------------------------------------------------------
' コンボボックス変更 → カラープレビュー更新
' ---------------------------------------------------------------

Private Sub cboOuterColor_Change()
    lblOuterColorPreview.BackColor = modChartFormatter.ColorNameToRGB(cboOuterColor.Text)
End Sub

Private Sub cboPlotColor_Change()
    lblPlotColorPreview.BackColor = modChartFormatter.ColorNameToRGB(cboPlotColor.Text)
End Sub

' ---------------------------------------------------------------
' フォントプレビュー更新
' ---------------------------------------------------------------

Private Sub cboFontName_Change()
    Call UpdateFontPreview
End Sub

Private Sub txtFontSize_Change()
    Call UpdateFontPreview
End Sub

Private Sub chkBold_Click()
    Call UpdateFontPreview
End Sub

Private Sub chkItalic_Click()
    Call UpdateFontPreview
End Sub

Private Sub UpdateFontPreview()
    On Error Resume Next
    If cboFontName.Text <> "" Then
        lblFontPreview.Font.Name = cboFontName.Text
    End If
    If IsNumeric(txtFontSize.Text) Then
        Dim sz As Double
        sz = CDbl(txtFontSize.Text)
        If sz >= 6 And sz <= 72 Then lblFontPreview.Font.Size = sz
    End If
    lblFontPreview.Font.bold = chkBold.Value
    lblFontPreview.Font.Italic = chkItalic.Value
    On Error GoTo 0
End Sub
