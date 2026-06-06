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
├── Auto Home                  G28
└── Soft Endstops           [on/off]
```

---

## Probe and Level（プローブ＆レベリング）

```
Probe and Level
├── Auto Home                  G28（未ホーミング時のみ表示）
├── Bed Leveling            [on/off]
├── UBL Leveling            →  ※下記サブメニュー参照
├── Level Bed                  G29（ホーミング済の場合）
├── Edit Mesh               →  メッシュ編集
├── Z Fade Height              高さ補正フェード(mm)
├── Manual Deploy              M401
├── Manual Stow                M402
├── Zprobe Offset X            プローブXオフセット
├── Zprobe Offset Y            プローブYオフセット
├── Babystep Z / Z Probe Wizard →
├── Zprobe Offset Z            プローブZオフセット
├── Z Probe Wizard          →  Zオフセットウィザード
├── M48 Probe Test             G28O + M48 P10
└── Store Settings             M500
```

### UBL Leveling サブメニュー

```
UBL Leveling
├── Activate UBL
├── Deactivate UBL
├── Step-By-Step UBL        →
├── Edit Mesh               →
│   └── Fine Tune Mesh      →
│       ├── Fine Tune All      G29P4RT
│       └── Fine Tune Closest  G29P4T
├── Mesh Height Adjust
├── Validate Mesh           →
│   ├── Validate PLA           G28 + G26CPI0
│   └── Validate ABS           G28 + G26CPI1
├── Grid Level              →
│   ├── 3-Point Leveling       G29J0
│   └── Grid Mesh Leveling
├── Mesh Storage            →
│   ├── Storage Slot
│   ├── Load Mesh
│   └── Save Mesh
└── Return to Status
```

---

## Temperature（温度設定）

```
Temperature
├── Nozzle:                 xxx °C（0〜275）
├── Bed:                    xxx °C（0〜100）
├── Fan Speed:              xxx（0〜255）
├── Preheat PLA             →
│   ├── Preheat PLA            ノズル+ベッド同時予熱
│   ├── Preheat PLA End        ノズルのみ予熱
│   ├── Preheat PLA All
│   └── Preheat PLA Bed        ベッドのみ予熱
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
├── Preheat PLA Conf        →
│   ├── Nozzle Temp
│   ├── Bed Temp
│   └── Store Settings
├── Preheat ABS Conf        →
│   ├── Nozzle Temp
│   ├── Bed Temp
│   └── Store Settings
├── BLTouch                 →  ※下記サブメニュー参照
├── Store Settings             M500（EEPROM保存）
├── Load Settings              M501（EEPROM読込）
└── Reset Settings             M502（初期化）
```

### Advanced Settings サブメニュー

```
Advanced Settings
├── Temperature             →
│   ├── PID Autotune E1
│   ├── Hotend PID P
│   ├── Hotend PID I
│   ├── Hotend PID D
│   ├── PID Autotune Bed
│   ├── Bed PID P
│   ├── Bed PID I
│   └── Bed PID D
├── Velocity Max            →
│   ├── Vmax X
│   ├── Vmax Y
│   ├── Vmax Z
│   ├── Vmax E
│   ├── Vmin
│   └── Vtrav Min
├── Max Acceleration        →
│   ├── Amax X
│   ├── Amax Y
│   ├── Amax Z
│   └── Amax E
├── Acceleration            →
│   ├── Accel
│   ├── A-Retract
│   └── A-Travel
├── Junction Deviation
├── Steps/mm                →
│   ├── X Steps/mm
│   ├── Y Steps/mm
│   ├── Z Steps/mm
│   └── E Steps/mm
└── Filament                →
    └── Fil. Runout Distance
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
├── 5V Mode             ※要確認
├── OD Mode             ※要確認
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
Tune（Main Menu → 印刷中）
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

