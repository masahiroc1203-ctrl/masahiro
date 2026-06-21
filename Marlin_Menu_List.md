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
├── Build Custom Mesh          温度指定してビルド（⚠️ Bug: 温度設定が無視される）
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
├── Output UBL Info            G29W（⚠️ 通常ビルドでは無動作 → 要 UBL_DEVEL_DEBUGGING）
│
└── Store Settings             M500（EEPROMへ保存）
```

---

## Gコード / Mコード リファレンス

### G28 系 — ホーミング

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G28` | Auto Home | 全軸ホーミング |
| `G28O` | M48 Probe Test（前処理） | 前回ホーム結果を使用（未ホーム時のみ実行） |

---

### G29 P系 — UBLフェーズ操作

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G29NP1` | Step 1: Build Cold Mesh | ホームせずにフェーズ1（全点プロービング） |
| `G29 P1` | Build Cold Mesh | G28後にフェーズ1 |
| `G29P1C` | Continue Mesh | 中断したP1を再開 |
| `G29P2BT0` | Manual Fill-in / Manual Mesh | 手動プローブで各点測定（LCDで誘導） |
| `G29P3T0` | Smart Fill-in / Step 2 | 補間で未測定点を自動補完 |
| `G29P3RC.{n}` | Fill-in Amount（スライダ） | 指定値でスムーズ補間（C=定数、R=繰返し） |
| `G29P4RT` | Fine Tune All / Step 4, 6 | 全点をプローブで精密調整（R=全点、T=LCD表示） |
| `G29P4T` | Fine Tune Closest | 最近点のみ精密調整 |
| `G29P4X{x}Y{y}R{n}` | Mesh Editor（クリック時） | 指定座標の点をプローブで精密調整 |

---

### G29 S / L 系 — メッシュ保存・読込

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G29S{n}` | Save Bed Mesh / Step 7 | スロットnにEEPROM保存 |
| `G29L{n}` | Load Bed Mesh | スロットnからEEPROM読込 |
| `G29S-1` | Off Printer Backup | メッシュをGコードとしてホスト（PC）へ出力 |

---

### G29 I 系 — 無効化

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G29I999` | Manual Mesh（前処理） | 全点をNaN（未測定）にリセット |
| `G29I` | Invalidate Closest | 最近点のみNaNにリセット |

---

### G29 T 系 — 出力

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G29T0` | Output for Host | メッシュをシリアルへテキスト出力 |
| `G29T1` | Output for CSV | メッシュをシリアルへCSV出力 |

---

### G29 J 系 — 傾き補正

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G29J0` | 3-Point Mesh Leveling | 3点でベッド傾き補正 |
| `G29J{n}` | Grid Mesh Leveling | nグリッドで傾き補正（n=2〜6） |

---

### G29 W 系 — デバッグ情報 ⚠️

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G29W` | Output UBL Info | **要 `UBL_DEVEL_DEBUGGING`。通常ビルドでは完全無動作（Bug 1）** |

---

### G26 系 — テスト印刷

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `G28\nG26CPI{preset}` | Validate PLA / ABS | ホーム後にプリセット温度でテスト印刷 |
| `G28\nG26CPH{hotend}B{bed}` | Validate Custom Mesh | カスタム温度でテスト印刷 |

---

### M 系

| コマンド | メニュー項目 | 動作 |
|---------|------------|------|
| `M48 P10` | M48 Probe Test | プローブ繰返し精度測定（10回） |
| `M401` | Manual Deploy | BLTouch手動展開 |
| `M402` | Manual Stow | BLTouch手動格納 |
| `M500` | Store Settings | 全設定をEEPROMへ保存 |
| `M501` | Load Settings | EEPROMから設定を読込 |
| `M502` | Reset Settings | 工場出荷時設定に戻す |
| `M1004 B{bed}H{hotend}S{slot}` | Mesh Wizard | 温度・スロット指定でメッシュ作成（2.x以降） |

---

### G29 パラメータ全一覧

#### Marlin 1.1.x から存在（UBL初期実装）

| パラメータ | 用途 | 備考 |
|-----------|------|------|
| `A` | UBL有効化 | `D` と同時指定不可 |
| `D` | UBL無効化 | |
| `P0〜P6` | フェーズ指定 | P5=平均補正、P6=高さシフト |
| `S` / `L` | 保存 / 読込 | `S-1` でGコードとしてエクスポート |
| `T` | トポロジーマップ出力 | `T0`=テキスト、`T1`=CSV |
| `I` | 測定点を無効化（NaN化） | 値=個数。`I999`で全点 |
| `J` | グリッド傾き補正 | `J0`=3点、`J2〜9`=グリッド |
| `B` | ビジネスカード厚み測定 | P2と併用 |
| `C` | 継続 / 定数（コンテキスト依存） | P1=継続、P3=補間定数 |
| `H` | ノズル高さオフセット | P2/P4と併用 |
| `R` | 繰返し回数 | 省略時=GRID_MAX_POINTS |
| `E` | 各プローブ後にストウ | P1と併用 |
| `V` | 詳細出力レベル（0〜4） | |
| `F` | フェード高さ設定（mm） | |
| `U` | 外周のみプローブ | P1と併用。素早い初期測定向け |
| `X` / `Y` | 操作対象の座標指定 | |
| `W` / `K` / `Q` | デバッグ専用 | 要 `UBL_DEVEL_DEBUGGING` |

#### Marlin 2.x で追加

| パラメータ / 機能 | 内容 |
|-----------------|------|
| `N`（内部用） | ホーム強制実行。`G29NP1` のようにメニューが内部で使用。ドキュメントに記載なし |
| `P3.1〜P3.13` | 加重最小二乗法（WLSF）補間。距離の重み付けを調整できる。`UBL_G29_P31` で有効化 |
| `UBL_HILBERT_CURVE` | P1プロービング順序をヒルベルト曲線順に変更（デフォルトはスパイラル） |
| `M1004`（Mesh Wizard） | 温度・スロット指定ワンクリック作成。`UBL_MESH_WIZARD` で有効化 |

---

## 既知のバグ（コードレビュー結果）

| # | 場所 | 内容 | 深刻度 |
|---|------|------|--------|
| Bug 1 | `menu_probe_level.cpp` | `G29W`（Output UBL Info）が `UBL_DEVEL_DEBUGGING` 未定義時に完全無動作。メニューには表示されるがシリアルに何も出力されない | 中 |
| Bug 2 | `menu_ubl.cpp` `_lcd_ubl_build_custom_mesh()` | `HAS_HEATED_BED` 条件が逆転しており、ベッドヒーター搭載機（Ender 3 Pro）でカスタム温度設定が完全に無視される | **高** |
| Bug 3 | `menu_ubl.cpp` `_menu_ubl_mesh_wizard()` | Mesh Wizardのスロット上限が `total_slots`（正しくは `total_slots - 1`）。Storage Meshメニューでは正しく `a - 1` を使用しているため不整合 | 低 |

### Bug 2 詳細（Build Custom Mesh 温度無視）

```cpp
// 現在のコード（誤）
#if HAS_HEATED_BED
  sprintf_P(ubl_lcd_gcode, PSTR("G28\nG29 P1"));          // 温度コマンドなし！
#else
  sprintf_P(ubl_lcd_gcode, PSTR("G28\nM109 S%i\nG29 P1"), custom_hotend_temp);
#endif

// 正しいコード
#if HAS_HEATED_BED
  sprintf_P(ubl_lcd_gcode, PSTR("G28\nM190 S%i\nM109 S%i\nG29 P1"),
            custom_bed_temp, custom_hotend_temp);
#else
  sprintf_P(ubl_lcd_gcode, PSTR("G28\nM109 S%i\nG29 P1"), custom_hotend_temp);
#endif
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
