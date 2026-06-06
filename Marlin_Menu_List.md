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
├── Move Axis               →
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
├── Auto Home                  G28（未ホーミング時のみ）
├── Bed Leveling            [on/off]（ホーミング済かつメッシュ有効時のみ）
├── UBL Leveling            →  ※下記サブメニュー参照
├── Edit Mesh               →  X/Y/Zポイント手動編集（基本エディタ）
├── Z Fade Height              高さ補正フェード(mm)
├── Manual Deploy              M401
├── Manual Stow                M402
├── Zprobe Offset X            プローブXオフセット
├── Zprobe Offset Y            プローブYオフセット
├── Babystep Z              →  Zオフセット＋ベイビーステップ調整
├── Z Probe Wizard          →  Zオフセットウィザード
├── M48 Probe Test             G28O + M48 P10
└── Store Settings             M500
```

---

## UBL Leveling サブメニュー

```
UBL Leveling
├── Bed Leveling            [on/off]
├── Z Fade Height
├── Step-By-Step UBL        →
│   ├── 1 Build Cold Mesh      G29NP1
│   ├── 2 Smart Fill-in        G29P3T0
│   ├── 3 Validate Mesh        →（G26検証）
│   ├── 4 Fine Tune All        G29P4RT
│   ├── 5 Validate Mesh        →（G26検証）
│   ├── 6 Fine Tune All        G29P4RT
│   └── 7 Save Bed Mesh
├── Mesh Wizard             →
│   ├── Hotend Temp
│   ├── Bed Temp
│   ├── Storage Slot
│   ├── Mesh Wizard（実行）
│   └── Validate Mesh       →
├── Mesh Editor                マップ画面（グリッド表示・直接編集）
├── Mesh Storage            →
│   ├── Storage Slot: [0-n]
│   ├── Load Bed Mesh
│   └── Save Bed Mesh
├── Output Map              →
│   ├── Output for Host        G29T0
│   ├── Output for CSV         G29T1
│   └── Off Printer Backup     G29S-1
├── UBL Tools               →
│   ├── Build Mesh          →
│   │   ├── Build Cold Mesh    G28 + G29P1
│   │   ├── Build Custom Mesh  →（温度指定ビルド）
│   │   ├── Fill-in Mesh       →
│   │   ├── Continue Mesh      G29P1C
│   │   ├── Invalidate All
│   │   └── Invalidate Closest G29I
│   ├── Manual Mesh            G29I999 + G29P2BT0
│   ├── Validate Mesh       →（G26）
│   ├── Edit Mesh           →
│   │   ├── Fine Tune All      G29P4RT
│   │   ├── Fine Tune Closest  G29P4T
│   │   └── Mesh Height Adjust
│   └── Mesh Leveling       →
│       ├── 3-Point Leveling   G29J0
│       └── Grid Mesh Leveling →
└── Output UBL Info            G29W
```

---

## Temperature（温度設定）

```
Temperature
├── Nozzle:                 xxx °C（0〜275）
├── Bed:                    xxx °C（0〜100）
├── Fan Speed:              xxx（0〜255）
├── Preheat PLA             →
│   ├── Preheat PLA            ノズル＋ベッド同時予熱
│   ├── Preheat PLA End        ノズルのみ
│   ├── Preheat PLA All
│   └── Preheat PLA Bed        ベッドのみ
├── Preheat ABS             →
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
├── Advanced Settings       →  ※下記サブメニュー参照
├── BLTouch                 →  ※下記サブメニュー参照
├── Runout Sensor           [on/off]
├── Preheat PLA Conf        →
│   ├── Nozzle Temp
│   ├── Bed Temp
│   └── Store Settings
├── Preheat ABS Conf        →
│   ├── Nozzle Temp
│   ├── Bed Temp
│   └── Store Settings
├── Store Settings             M500（EEPROM保存）
├── Load Settings              M501（EEPROM読込）
└── Reset Settings             M502（工場出荷時設定に戻す）
```

### Advanced Settings サブメニュー

```
Advanced Settings
├── Temperature             →
│   ├── PID Autotune E1
│   ├── Hotend PID P / I / D
│   ├── PID Autotune Bed
│   └── Bed PID P / I / D
├── Velocity Max            →
│   ├── Vmax X / Y / Z / E
│   ├── Vmin
│   └── Vtrav Min
├── Max Acceleration        →
│   └── Amax X / Y / Z / E
├── Acceleration            →
│   ├── Accel（印刷）
│   ├── A-Retract
│   └── A-Travel
├── Junction Deviation
├── Steps/mm                →
│   └── X / Y / Z / E Steps/mm
└── Filament                →
    ├── Fil. Unload
    ├── Fil. Load
    └── Runout Distance
```

### BLTouch サブメニュー

```
BLTouch
├── Reset
├── Self Test
├── Deploy
├── Stow
├── SW Mode
├── Speed Mode          [on/off]
├── 5V Mode
├── OD Mode
├── Mode Store
├── Mode Store 5V
├── Mode Store OD
└── Mode Echo
```

---

## About Printer（プリンタ情報）

```
About Printer
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
