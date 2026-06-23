Attribute VB_Name = "modChartFormatter"
Option Explicit

' ==============================================================
' グラフ書式設定マクロ - チャートロジックモジュール
' ==============================================================

Private Const MENU_CAPTION As String = "グラフ書式設定(&F)..."

' --------------------------------------------------------------
' コンテキストメニュー管理
' --------------------------------------------------------------

Public Sub AddChartContextMenu()
    Dim oBar As CommandBar
    Dim oBtn As CommandBarButton

    Call RemoveChartContextMenu

    On Error GoTo ErrHandler
    Set oBar = Application.CommandBars("Chart")
    Set oBtn = oBar.Controls.Add(Type:=msoControlButton, Temporary:=True)
    With oBtn
        .Caption = MENU_CAPTION
        .OnAction = "modChartFormatter.ShowChartFormatter"
        .BeginGroup = True
    End With
    Exit Sub

ErrHandler:
    MsgBox "メニューの追加に失敗しました: " & Err.Description, vbExclamation, "グラフ書式設定"
End Sub

Public Sub RemoveChartContextMenu()
    On Error Resume Next
    Application.CommandBars("Chart").Controls(MENU_CAPTION).Delete
    On Error GoTo 0
End Sub

' --------------------------------------------------------------
' フォーム表示
' --------------------------------------------------------------

Public Sub ShowChartFormatter()
    If ActiveChart Is Nothing Then
        MsgBox "グラフをクリックして選択してから実行してください。", _
               vbExclamation, "グラフ書式設定"
        Exit Sub
    End If
    Load frmChartFormatter
    frmChartFormatter.Show vbModeless
End Sub

' --------------------------------------------------------------
' 軸ラベル設定
' --------------------------------------------------------------

Public Sub SetAxisTitle(cht As Chart, axisType As XlAxisType, _
                        hasTitle As Boolean, titleText As String)
    On Error Resume Next
    With cht.Axes(axisType)
        .HasTitle = hasTitle
        If hasTitle Then .AxisTitle.Text = titleText
    End With
    On Error GoTo 0
End Sub

' --------------------------------------------------------------
' グラフサイズ設定
' --------------------------------------------------------------

Public Sub SetChartSize(cht As Chart, w As Double, h As Double, useCm As Boolean)
    Dim obj As Object
    Set obj = cht.Parent

    If TypeName(obj) <> "ChartObject" Then
        MsgBox "埋め込みグラフのみサイズ変更が可能です。", vbInformation, "グラフ書式設定"
        Exit Sub
    End If

    If useCm Then
        If w > 0 Then obj.Width = Application.CentimetersToPoints(w)
        If h > 0 Then obj.Height = Application.CentimetersToPoints(h)
    Else
        If w > 0 Then obj.Width = w
        If h > 0 Then obj.Height = h
    End If
End Sub

' --------------------------------------------------------------
' フォント設定
' targetFlags ビット: 1=ChartArea, 2=Title, 4=Axes, 8=Legend
' --------------------------------------------------------------

Public Sub SetChartFont(cht As Chart, fontName As String, fontSize As Double, _
                        bold As Boolean, italic As Boolean, targetFlags As Integer)
    On Error Resume Next

    If targetFlags And 1 Then
        Call ApplyFontToObj(cht.ChartArea.Font, fontName, fontSize, bold, italic)
    End If

    If targetFlags And 2 Then
        If cht.HasTitle Then
            Call ApplyFontToObj(cht.ChartTitle.Font, fontName, fontSize, bold, italic)
        End If
    End If

    If targetFlags And 4 Then
        Dim ax As Axis
        For Each ax In cht.Axes
            Call ApplyFontToObj(ax.TickLabels.Font, fontName, fontSize, bold, italic)
            If ax.HasTitle Then
                Call ApplyFontToObj(ax.AxisTitle.Font, fontName, fontSize, bold, italic)
            End If
        Next ax
    End If

    If targetFlags And 8 Then
        If cht.HasLegend Then
            Call ApplyFontToObj(cht.Legend.Font, fontName, fontSize, bold, italic)
        End If
    End If

    On Error GoTo 0
End Sub

Private Sub ApplyFontToObj(oFont As Object, fontName As String, fontSize As Double, _
                            bold As Boolean, italic As Boolean)
    If fontName <> "" Then oFont.Name = fontName
    If fontSize > 0 Then oFont.Size = fontSize
    oFont.bold = bold
    oFont.Italic = italic
End Sub

' --------------------------------------------------------------
' 枠線設定
' --------------------------------------------------------------

Public Sub SetChartBorder(cht As Chart, isOuter As Boolean, _
                           show As Boolean, lineStyle As Long, _
                           weightPt As Double, colorRGB As Long)
    Dim oBorder As Object

    On Error GoTo ErrExit
    If isOuter Then
        Set oBorder = cht.ChartArea.Border
    Else
        Set oBorder = cht.PlotArea.Border
    End If

    If show Then
        oBorder.LineStyle = lineStyle
        oBorder.Weight = weightPt
        oBorder.Color = colorRGB
    Else
        oBorder.LineStyle = xlNone
    End If
ErrExit:
End Sub

' --------------------------------------------------------------
' ユーティリティ（modFormLogic から呼び出し）
' --------------------------------------------------------------

Public Function ColorNameToRGB(colorName As String) As Long
    Select Case colorName
        Case "黒":       ColorNameToRGB = RGB(0, 0, 0)
        Case "白":       ColorNameToRGB = RGB(255, 255, 255)
        Case "赤":       ColorNameToRGB = RGB(192, 0, 0)
        Case "青":       ColorNameToRGB = RGB(0, 70, 127)
        Case "緑":       ColorNameToRGB = RGB(0, 112, 0)
        Case "黄":       ColorNameToRGB = RGB(255, 217, 0)
        Case "橙":       ColorNameToRGB = RGB(255, 127, 0)
        Case "紫":       ColorNameToRGB = RGB(112, 48, 160)
        Case "灰":       ColorNameToRGB = RGB(127, 127, 127)
        Case "水":       ColorNameToRGB = RGB(0, 176, 240)
        Case Else:       ColorNameToRGB = RGB(0, 0, 0)
    End Select
End Function

Public Function LineStyleNameToConst(styleName As String) As Long
    Select Case styleName
        Case "実線":     LineStyleNameToConst = xlContinuous
        Case "破線":     LineStyleNameToConst = xlDash
        Case "点線":     LineStyleNameToConst = xlDot
        Case "一点鎖線": LineStyleNameToConst = xlDashDot
        Case Else:       LineStyleNameToConst = xlContinuous
    End Select
End Function

Public Function WeightNameToPt(weightName As String) As Double
    Select Case weightName
        Case "0.25pt": WeightNameToPt = 0.25
        Case "0.5pt":  WeightNameToPt = 0.5
        Case "1pt":    WeightNameToPt = 1
        Case "1.5pt":  WeightNameToPt = 1.5
        Case "2pt":    WeightNameToPt = 2
        Case "2.5pt":  WeightNameToPt = 2.5
        Case "3pt":    WeightNameToPt = 3
        Case Else:     WeightNameToPt = 1
    End Select
End Function

Public Function GetCurrentChartSizeCm(cht As Chart, getWidth As Boolean) As Double
    On Error GoTo ErrExit
    Dim obj As Object
    Set obj = cht.Parent
    If TypeName(obj) = "ChartObject" Then
        If getWidth Then
            GetCurrentChartSizeCm = Application.Round( _
                obj.Width / Application.CentimetersToPoints(1), 2)
        Else
            GetCurrentChartSizeCm = Application.Round( _
                obj.Height / Application.CentimetersToPoints(1), 2)
        End If
    End If
    Exit Function
ErrExit:
    GetCurrentChartSizeCm = 0
End Function
