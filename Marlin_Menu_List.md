# Marlin 2.1.x メニュー一覧

対象機: **Ender 3 Pro / Creality V4.2.7 / BLTouch / UBL**  
ファームウェア: Marlin 2.1.x (カスタムビルド)

---

## メインメニュー（非印刷時）

```
Main Menu
├── [SDカード → ファイル一覧]
├── Motion                  →
├── Probe and Level         →
├── Change Filament
├── Temperature             →
├── Configuration           →
└── About Printer           →
```

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

## Probe and Level（プローブ＆レベリング）

```
Probe and Level
← Main Menu
├── Auto Home                  G28（未ホーミング時のみ）
├── UBL                     →  ※下記サブメニュー参照
├── Mesh Point Edit         →  X/Y座標を選んでZ値を直接入力する基本エディタ
│   ← Probe and Level          ※ lcd表示は "Edit Mesh"
│   ├── Mesh X: [0-n]
│   ├── Mesh Y: [0-n]
│   └── Z Pos: x.xxx mm
├── Z Fade Height              高さ補正フェード(mm)
├── Manual Deploy              M401（BLTouch手動展開）
├── Manual Stow                M402（BLTouch手動格納）
├── Zprobe Offset X            プローブXオフセット（ノズルからの物理距離）
├── Zprobe Offset Y            プローブYオフセット（ノズルからの物理距離）
├── Babystep Z              →  印刷中も含めたZオフセット微調整
├── Z Probe Wizard          →  Zオフセット設定ウィザード
├── M48 Probe Test             G28O + M48 P10（プローブ繰返し精度測定）
└── Store Settings             M500（EEPROMへ保存）
```

---

## UBL（Unified Bed Leveling）

> LCD実機の表示は "UBL Leveling"。  
> UBL = Unified Bed Leveling（統一ベッドレベリング）

```
UBL
← Probe and Level
├── Bed Leveling            [on/off]  メッシュ補正を印刷に適用するかどうか
│                                     ※ Probe and Level 側と同一設定
├── Z Fade Height              高さ補正フェード
├── Step-By-Step            →  初回メッシュ作成の手順ガイド（推奨）
│   ← UBL
│   ├── 1 Build Cold Mesh      G29NP1（冷間でプローブ自動測定）
│   ├── 2 Smart Fill-in        G29P3T0（未測定点を補間）
│   ├── 3 Validate Mesh     →  G26テスト印刷で目視確認
│   ├── 4 Fine Tune All        G29P4RT（全点精密調整）
│   ├── 5 Validate Mesh     →  再確認
│   ├── 6 Fine Tune All        G29P4RT（最終調整）
│   └── 7 Save Bed Mesh        EEPROMスロットへ保存
├── Mesh Wizard             →  温度指定してワンクリックでメッシュ作成
│   ← UBL
│   ├── Hotend Temp
│   ├── Bed Temp
│   ├── Storage Slot
│   ├── Mesh Wizard（実行）
│   └── Validate Mesh       →
├── Mesh Editor                グリッドマップ表示・各点を直接ノブで調整
│                              ※ Step-By-Step の Fine Tune に相当
├── Mesh Storage            →  メッシュのEEPROMスロット管理
│   ← UBL
│   ├── Storage Slot: [0-n]
│   ├── Load Bed Mesh
│   └── Save Bed Mesh
├── Output Map              →  メッシュデータを出力
│   ← UBL
│   ├── Output for Host        G29T0（ホストに送信）
│   ├── Output for CSV         G29T1（CSV形式）
│   └── Off Printer Backup     G29S-1
├── UBL Tools               →
│   ← UBL
│   ├── Build Mesh          →  メッシュ作成メニュー
│   │   ← UBL Tools
│   │   ├── Build Cold Mesh    G28 + G29P1（自動プローブ）
│   │   ├── Build Custom Mesh  →（温度指定してビルド）
│   │   ├── Fill-in Mesh    →（未測定点補間）
│   │   ├── Continue Mesh      G29P1C（中断したメッシュを継続）
│   │   ├── Invalidate All     全点を無効化
│   │   └── Invalidate Closest G29I（最近点を無効化）
│   ├── Manual Mesh            G29I999 + G29P2BT0（手動で点を測定）
│   ├── Validate Mesh       →  G26テスト印刷で目視確認
│   ├── Mesh Fine-Tune      →  プローブで精密調整
│   │   ← UBL Tools            ※ LCD表示は "Edit Mesh"（Probe and Levelのとは別機能）
│   │   ├── Fine Tune All      G29P4RT（全点をプローブで再測定・調整）
│   │   ├── Fine Tune Closest  G29P4T（最近点のみ）
│   │   └── Mesh Height Adjust 全体的な高さシフト
│   └── Mesh Leveling       →
│       ← UBL Tools
│       ├── 3-Point Leveling   G29J0
│       └── Grid Mesh Leveling →
└── Output UBL Info            G29W（UBL状態をホストへ出力）
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
│   ├── Preheat ABS
│   ├── Preheat ABS End
│   ├── Preheat ABS All
│   └── Preheat ABS Bed
└── Cooldown                   全ヒーターOFF
```

---

## Configuration（設定）

```
Configuration
← Main Menu
├── Advanced Settings       →
│   ← Configuration
│   ├── Temperature         →
│   │   ├── PID Autotune E1
│   │   ├── Hotend PID P / I / D
│   │   ├── PID Autotune Bed
│   │   └── Bed PID P / I / D
│   ├── Velocity Max        →
│   │   ├── Vmax X / Y / Z / E
│   │   ├── Vmin
│   │   └── Vtrav Min
│   ├── Max Acceleration    →
│   │   └── Amax X / Y / Z / E
│   ├── Acceleration        →
│   │   ├── Accel（印刷）
│   │   ├── A-Retract
│   │   └── A-Travel
│   ├── Junction Deviation
│   ├── Steps/mm            →
│   │   └── X / Y / Z / E Steps/mm
│   └── Filament            →
│       ├── Fil. Unload
│       ├── Fil. Load
│       └── Runout Distance
├── BLTouch                 →
│   ← Configuration
│   ├── Reset
│   ├── Self Test
│   ├── Deploy
│   ├── Stow
│   ├── SW Mode
│   ├── Speed Mode          [on/off]
│   ├── 5V Mode
│   ├── OD Mode
│   ├── Mode Store
│   ├── Mode Store 5V
│   ├── Mode Store OD
│   └── Mode Echo
├── Runout Sensor           [on/off]
├── Preheat PLA Conf        →
│   ← Configuration
│   ├── Nozzle Temp
│   ├── Bed Temp
│   └── Store Settings
├── Preheat ABS Conf        →
│   ← Configuration
│   ├── Nozzle Temp
│   ├── Bed Temp
│   └── Store Settings
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

| 項目 | 場所 | 役割 |
|------|------|------|
| Probe X/Y Offset | Probe and Level | BLTouchの物理取付オフセット |
| Babystep Z | Probe and Level | Zオフセット微調整（印刷中も反映） |
| Bed Leveling [on/off] | UBL | メッシュ補正を印刷に適用するか |
| Mesh Point Edit | Probe and Level | X/Y座標を選んでZ値を数値入力 |
| Mesh Fine-Tune | UBL Tools | プローブで実測して自動調整 |
| Mesh Editor | UBL | グリッドマップでノブ直接操作 |
| Validate Mesh | UBL / UBL Tools | G26でテスト印刷→目視確認 |

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
