# Marlin 2.1.x メニュー一覧

対象機: **Ender 3 Pro / Creality V4.2.7 / BLTouch / UBL**  
ファームウェア: Marlin 2.1.x (カスタムビルド)

---

## メインメニュー（非印刷時）

```
Main Menu
├── [SDカード → ファイル一覧]
├── Motion                  →
├── Bed Leveling            →
├── Change Filament
├── Temperature             →
├── Configuration           →
└── About Printer           →
```

> LCD実機の表示は **"Probe and Level"**

---

## Motion（軸操作）

```
Motion
← Main Menu
├── Move Axis               →
│   ← Motion
│   ├── Move X              →  10mm / 1mm / 0.1mm
│   ├── Move Y              →  10mm / 1mm / 0.1mm
│   ├── Move Z              →  10mm / 1mm / 0.1mm
│   └── Move E              →  10mm / 1mm / 0.1mm
│   ※ 未ホーミング時は Move X/Y/Z の代わりに Auto Home が表示
├── Auto Home                  G28
└── Disable Steppers           M84
```

---

## Bed Leveling（ベッドレベリング）

> LCD実機の表示は **"Probe and Level"** と **"UBL Leveling"** の2階層  
> ここでは機能別にまとめて表示

```
Bed Leveling
← Main Menu
├── Auto Home                  G28（未ホーミング時のみ）
│
├─ [補正の適用]──────────────────────────────────────────
├── Bed Leveling            [on/off]  メッシュ補正を印刷に適用するかどうか
├── Z Fade Height              補正フェード高さ（mm）
│
├─ [プローブ設定]────────────────────────────────────────
├── Zprobe Offset X            BLTouchのノズルからのX物理距離
├── Zprobe Offset Y            BLTouchのノズルからのY物理距離
├── Babystep Z              →  Zオフセット微調整（印刷中も反映）
├── Z Probe Wizard          →  Zオフセット設定ウィザード
├── M48 Probe Test             G28O + M48 P10（プローブ繰返し精度測定）
├── Manual Deploy              M401（BLTouch手動展開）
├── Manual Stow                M402（BLTouch手動格納）
│
├─ [メッシュ作成]────────────────────────────────────────
├── Step-By-Step            →  初回メッシュ作成の手順ガイド（推奨）
│   ← Bed Leveling
│   ├── 1 Build Cold Mesh      G29NP1　　プローブで全面自動測定
│   ├── 2 Smart Fill-in        G29P3T0　 未測定点を補間
│   ├── 3 Validate Mesh     →  G26テスト印刷→目視確認
│   ├── 4 Fine Tune All        G29P4RT　 全点をプローブで精密調整
│   ├── 5 Validate Mesh     →  再確認
│   ├── 6 Fine Tune All        G29P4RT　 最終調整
│   └── 7 Save Bed Mesh        EEPROMスロットへ保存
├── Mesh Wizard             →  温度・スロット指定してワンクリック作成
│   ← Bed Leveling
│   ├── Hotend Temp / Bed Temp / Storage Slot
│   └── Mesh Wizard（実行）
├── Build Cold Mesh            G28 + G29P1　プローブで全面自動測定
├── Build Custom Mesh          温度指定してビルド
├── Continue Mesh              G29P1C　中断したメッシュを継続
├── Manual Mesh                手動プローブ（BLTouch不使用）
├── Invalidate All             全測定値をクリア
├── Invalidate Closest         G29I　最近点のみクリア
│
├─ [メッシュ調整・確認]──────────────────────────────────
├── Mesh Point Edit            X/Y座標を選んでZ値を数値入力
│   ← Bed Leveling            ※ LCD表示は "Edit Mesh"
│   ├── Mesh X: [0-n]
│   ├── Mesh Y: [0-n]
│   └── Z Pos: x.xxx mm
├── Mesh Editor                グリッドマップ表示・ノブで各点を直接操作
├── Fine Tune All              G29P4RT　全点をプローブで再測定・調整
├── Fine Tune Closest          G29P4T　　最近点のみ
├── Validate Mesh           →  G26テスト印刷で目視確認
│   ← Bed Leveling
│   ├── Validate PLA           G28 + G26（PLA設定で印刷）
│   └── Validate ABS
│
├─ [保存・読込]──────────────────────────────────────────
├── Storage Slot: [0-n]
├── Save Bed Mesh
├── Load Bed Mesh
│
├─ [出力・情報]──────────────────────────────────────────
├── Output for Host            G29T0（シリアルへ送信）
├── Output for CSV             G29T1
├── Off Printer Backup         G29S-1
├── Output UBL Info            G29W（UBL状態をシリアルへ出力）
│
└── Store Settings             M500（EEPROMへ保存）
```

---

## Temperature（温度設定）

```
Temperature
← Main Menu
├── Nozzle:                 xxx °C（0〜275）
├── Bed:                    xxx °C（0〜100）
├── Fan Speed:              xxx（0〜255）
├── Preheat PLA             →
│   ← Temperature
│   ├── Preheat PLA            ノズル＋ベッド同時予熱
│   ├── Preheat PLA End        ノズルのみ
│   ├── Preheat PLA All
│   └── Preheat PLA Bed        ベッドのみ
├── Preheat ABS             →
│   ← Temperature
│   └── Preheat ABS / End / All / Bed
└── Cooldown                   全ヒーターOFF
```

---

## Configuration（設定）

```
Configuration
← Main Menu
├── Advanced Settings       →
│   ← Configuration
│   ├── Temperature         →  PID設定（ノズル・ベッド）
│   ├── Velocity Max        →  Vmax X/Y/Z/E、Vmin、Vtrav Min
│   ├── Max Acceleration    →  Amax X/Y/Z/E
│   ├── Acceleration        →  印刷・リトラクト・トラベル
│   ├── Junction Deviation
│   ├── Steps/mm            →  X/Y/Z/E Steps/mm
│   └── Filament            →  Load/Unload量、Runout Distance
├── BLTouch                 →
│   ← Configuration
│   ├── Reset / Self Test / Deploy / Stow
│   ├── SW Mode / Speed Mode [on/off]
│   └── 5V Mode / OD Mode / Mode Store / Mode Echo
├── Runout Sensor           [on/off]
├── Preheat PLA Conf        →  ノズル温度・ベッド温度・Store Settings
├── Preheat ABS Conf        →  ノズル温度・ベッド温度・Store Settings
├── Store Settings             M500（EEPROMへ保存）
├── Load Settings              M501（EEPROMから読込）
└── Reset Settings             M502（工場出荷時設定に戻す）
```

---

## About Printer（プリンタ情報）

```
About Printer
← Main Menu
├── Firmware Info
├── Printer Info
└── Stats（印刷統計）
```

---

## 印刷中メニュー（Tune）

```
Main Menu（印刷中）
├── Pause Print
├── Stop Print
├── Tune                    →
│   ← Main Menu
│   ├── Speed:              xxx%
│   ├── Mesh Z Offset          ライブZオフセット
│   ├── Nozzle:             xxx °C
│   ├── Bed:                xxx °C
│   ├── Fan Speed:          xxx
│   ├── Flow:               xxx%
│   └── Babystep Z          →
└── Change Filament
```

---

## 機能早見表

| 機能 | 役割 |
|------|------|
| Bed Leveling [on/off] | メッシュ補正を印刷に適用するか |
| Probe X/Y Offset | BLTouchの物理取付オフセット |
| Babystep Z | Zオフセット微調整（印刷中も反映） |
| Mesh Point Edit | X/Y座標→Z値を数値で直接入力 |
| Mesh Editor | グリッドマップでノブ直接操作 |
| Fine Tune | プローブで実測して自動調整 |
| Validate Mesh | G26テスト印刷→目視確認 |
| Step-By-Step | 上記を順番にガイド（初回向け）|

---

## 備考

| 設定 | 値 |
|------|----|
| Preheat PLA ノズル | 210°C |
| Preheat PLA ベッド | 60°C |
| Preheat ABS ノズル | 240°C |
| Preheat ABS ベッド | 110°C |
| レベリング方式 | UBL（Unified Bed Leveling） |
| プローブ | BLTouch |
| プローブ温度待ち | 無効（PREHEAT_BEFORE_PROBING OFF）|
| レベリング温度待ち | 無効（PREHEAT_BEFORE_LEVELING OFF）|
