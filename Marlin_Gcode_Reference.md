# Marlin G-code / M-code リファレンス（UBL + BLTouch）

対象機: **Ender 3 Pro / Creality V4.2.7 / BLTouch / UBL**  
ファームウェア: Marlin 2.1.x (カスタムビルド)  
関連: [[Marlin_Menu_List]]

---

## G28 — ホーミング

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G28` | Auto Home | 全軸ホーミング |
| `G28O` | M48 Probe Test（前処理） | 既ホーム時はスキップ、未ホーム時のみ実行 |

---

## G29 — Unified Bed Leveling

### フェーズ操作（P系）

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G29NP1` | Step 1: Build Cold Mesh | ホームスキップ+フェーズ1（全点プロービング） |
| `G29 P1` | Build Cold Mesh | G28後にフェーズ1 |
| `G29P1C` | Continue Mesh | 中断したP1を再開 |
| `G29P2BT0` | Manual Fill-in / Manual Mesh | 手動プローブで各点測定（LCD誘導） |
| `G29P3T0` | Smart Fill-in / Step 2 | 補間で未測定点を自動補完 |
| `G29P3RC.{n}` | Fill-in Amount（スライダ） | 指定値でスムーズ補間（C=定数、R=全点繰返し） |
| `G29P4RT` | Fine Tune All / Step 4, 6 | 全点をプローブで精密調整（R=全点、T=LCD表示） |
| `G29P4T` | Fine Tune Closest | 最近点のみ精密調整 |
| `G29P4X{x}Y{y}R{n}` | Mesh Editor（クリック時） | 指定座標をプローブで精密調整 |

### 保存・読込（S / L 系）

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G29S{n}` | Save Bed Mesh / Step 7 | スロットnにEEPROM保存 |
| `G29L{n}` | Load Bed Mesh | スロットnからEEPROM読込 |
| `G29S-1` | Off Printer Backup | メッシュをGコードとしてホスト（PC）へ出力 |

### 無効化（I 系）

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G29I999` | Manual Mesh（前処理） | 全点をNaN（未測定）にリセット |
| `G29I` | Invalidate Closest | 最近点のみNaNにリセット |

### 出力（T 系）

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G29T0` | Output for Host | メッシュをシリアルへテキスト出力 |
| `G29T1` | Output for CSV | メッシュをシリアルへCSV出力 |

### 傾き補正（J 系）

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G29J0` | 3-Point Mesh Leveling | 3点でベッド傾き補正 |
| `G29J{n}` | Grid Mesh Leveling | nグリッドで傾き補正（n=2〜6） |

### デバッグ（W 系）⚠️

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G29W` | Output UBL Info | **⚠️ 要 `UBL_DEVEL_DEBUGGING`。通常ビルドでは完全無動作（Bug 1）** |

---

## G26 — テスト印刷（Mesh Validation）

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G28\nG26CPI{preset}` | Validate PLA / ABS | ホーム後プリセット温度でテスト印刷（ベッドあり） |
| `G28\nG26CPB0I{preset}` | Validate PLA / ABS | ホーム後プリセット温度でテスト印刷（ベッドなし） |
| `G28\nG26CPH{hotend}B{bed}` | Validate Custom Mesh | カスタム温度でテスト印刷 |

---

## G34 — Z軸整列

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `G34` | Auto Z-Align | デュアルZ軸の自動アライメント |

---

## M コード

| コマンド | 発行元メニュー | 動作 |
|---------|--------------|------|
| `M48 P10` | M48 Probe Test | プローブ繰返し精度測定（10回） |
| `M84` | Disable Steppers | 全ステッパーモーター無効化 |
| `M109 S{n}` | Build Custom Mesh（ベッドなし機のみ） | ノズル温度待ち |
| `M190 S{n}` | Build Custom Mesh（本来の正しい動作） | ベッド温度待ち（Bug 2修正後） |
| `M401` | Manual Deploy | BLTouch手動展開 |
| `M402` | Manual Stow | BLTouch手動格納 |
| `M500` | Store Settings | 全設定をEEPROMへ保存 |
| `M501` | Load Settings | EEPROMから設定を読込 |
| `M502` | Reset Settings | 工場出荷時設定に戻す |
| `M1004 B{bed}H{hotend}S{slot}` | Mesh Wizard | 温度・スロット指定でメッシュ作成（2.x以降） |

---

## G29 パラメータ 全一覧

### Marlin 1.1.x から存在（UBL初期実装）

| パラメータ | 用途 | 主な組み合わせ |
|-----------|------|--------------|
| `A` | UBL有効化 | 単独 |
| `D` | UBL無効化 | 単独 |
| `P0` | メッシュデータをゼロクリア | 単独 |
| `P1` | 自動プロービング（全面測定） | `C`=継続、`T`=表示、`E`=ストウ、`U`=外周のみ |
| `P2` | 手動プローブ（未到達点） | `B`=カード測定、`H`=高さ、`C`=連続 |
| `P3` | 未測定点を補間 | `T0`=スマート、`C{val}`=定数、`R`=繰返し |
| `P4` | Fine Tune（精密調整） | `R`=繰返し、`T`=表示、`X/Y`=位置、`H`=オフセット |
| `P5` | 平均高さ・標準偏差算出 | `C`=自動補正（P6を呼ぶ） |
| `P6` | メッシュ全体をCの値だけシフト | `C{val}` |
| `S` / `L` | 保存 / 読込 | `S{n}`, `L{n}`, `S-1`=エクスポート |
| `T` | トポロジーマップ出力 | `T0`=テキスト、`T1`=CSV |
| `I` | 測定点を無効化 | `I{n}`=n点、`I999`=全点 |
| `J` | グリッド傾き補正 | `J0`=3点、`J2〜9`=グリッド |
| `B` | ビジネスカード厚み測定 | P2と組み合わせ |
| `C` | 継続 / 定数（コンテキスト依存） | P1=継続、P3=補間定数 |
| `H` | ノズル高さオフセット | P2/P4と組み合わせ |
| `R` | 繰返し回数 | 省略時=GRID_MAX_POINTS |
| `E` | 各プローブ後にストウ | P1と組み合わせ |
| `V` | 詳細出力レベル（0〜4） | 単独 |
| `F` | フェード高さ設定（mm） | 単独 |
| `U` | 外周のみプローブ（素早い初期測定） | P1と組み合わせ |
| `X` / `Y` | 操作対象の座標指定 | 各種Pと組み合わせ |
| `W` | UBL情報表示 | **要 `UBL_DEVEL_DEBUGGING`** |
| `K` | 2つのメッシュを差分比較 | **要 `UBL_DEVEL_DEBUGGING`** |
| `Q` | テストパターン生成 | **要 `UBL_DEVEL_DEBUGGING`**（Q-1はEEPROMダンプ） |

### Marlin 2.x で追加

| パラメータ / 機能 | 内容 | 備考 |
|-----------------|------|------|
| `N` | ホーム強制実行 | **内部専用**。ドキュメント未記載。メニューが `G29NP1` として使用 |
| `P3.1〜P3.13` | 加重最小二乗法（WLSF）補間 | `UBL_G29_P31` で有効化。距離の重み付けを変更可能 |
| `UBL_HILBERT_CURVE` | P1プロービング順序をヒルベルト曲線順に変更 | 現在このビルドでは無効 |
| `M1004` | Mesh Wizard（ワンクリック作成） | `UBL_MESH_WIZARD` で有効化 |

---

## 既知のバグ

### Bug 1: Output UBL Info（G29W）が無動作

**場所**: `menu_probe_level.cpp`  
**深刻度**: 中

```cpp
// ubl_G29.cpp
#if ENABLED(UBL_DEVEL_DEBUGGING)   // 通常ビルドでは未定義
  if (parser.seen_test('W')) g29_what_command();
#endif
```

**修正案**: `Configuration_adv.h` で `#define UBL_DEVEL_DEBUGGING` を有効にするか、メニューからこの項目を削除する。

---

### Bug 2: Build Custom Mesh が温度設定を無視 ⚠️ 重要

**場所**: `menu_ubl.cpp` — `_lcd_ubl_build_custom_mesh()`  
**深刻度**: 高

```cpp
// 現在のコード（誤）— HAS_HEATED_BED の条件が逆転している
#if HAS_HEATED_BED
  sprintf_P(ubl_lcd_gcode, PSTR("G28\nG29 P1"));           // 温度コマンドなし！
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

**影響**: Ender 3 Pro は `HAS_HEATED_BED=真` のため、カスタム温度設定が常に無視され、常温でメッシュ作成される。

---

### Bug 3: Mesh Wizard のスロット上限が1つオーバー

**場所**: `menu_ubl.cpp` — `_menu_ubl_mesh_wizard()`  
**深刻度**: 低

```cpp
// 現在（誤）: total_slots は例えば5。有効範囲は0〜4なのに上限5を指定
EDIT_ITEM(int3, MSG_UBL_STORAGE_SLOT, &ubl_storage_slot, 0, total_slots);

// 正しくは
EDIT_ITEM(int3, MSG_UBL_STORAGE_SLOT, &ubl_storage_slot, 0, total_slots - 1);
```

**参考**: Storage Mesh メニューでは正しく `a - 1` を使用している。

---

## 参考

- [[Marlin_Menu_List]] — LCD メニュー全体の階層構造
- [Marlin G29 UBL Documentation](https://marlinfw.org/docs/gcode/G029-ubl.html)
