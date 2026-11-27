# Ender-3 Pro ファームウェア（作り直し版）

公式 **Marlin 2.1.3（安定版）** の素の設定に、このプリンタに必要な変更だけを当てたもの。
以前の設定（Creality の例をもとに継ぎ足したもの）は使っていない。Creality の例は参考にとどめた。

## 対象ハード

| 項目 | 内容 |
|---|---|
| 本体 | Creality Ender-3 Pro（Z 軸に LM ガイド追加） |
| 基板 | Creality 4.2.7（STM32F103RE、TMC2208 スタンドアロン） |
| 画面 | 純正の回転ノブ式 12864 液晶 |
| 押出機 | Sprite Extruder Pro（ダイレクトドライブ、E = 424.9 steps/mm） |
| プローブ | BLTouch（専用ピン PB0 / PB1） |
| レベリング | UBL（5 × 5） |
| 造形範囲 | 220 × 220 × 245 mm（実測） |
| ホスト | ラズパイ 4 の OctoPrint（USB、115200 bps） |

## ファイル

| パス | 内容 |
|---|---|
| `tools/apply_config.py` | 素の Marlin 2.1.3 設定から、このハード用の設定を作るスクリプト。**変更点はすべてこの中の一覧にある** |
| `config/Configuration.h` / `config/Configuration_adv.h` | 上のスクリプトで作った設定（Marlin の `Marlin/` フォルダにそのまま置く） |

### 作り直し方

```bash
git clone --depth 1 --branch 2.1.3 https://github.com/MarlinFirmware/Marlin
python3 tools/apply_config.py Marlin/Marlin config
cp config/Configuration*.h Marlin/Marlin/
cd Marlin && pio run -e STM32F103RE_creality
# → .pio/build/STM32F103RE_creality/firmware-*.bin を SD カードに置いて電源投入
```

## 以前の設定から外したもの

| 項目 | 理由 |
|---|---|
| `FILAMENT_RUNOUT_SENSOR` | センサーが付いていない。有効のままだと誤検知で止まる原因になる |
| `PROBE_X/Y/Z_OFFSET` 独自マクロ、`MESH_MIN/MAX_*` の手書き | Marlin 標準の `NOZZLE_TO_PROBE_OFFSET` と `PROBING_MARGIN` で自動計算させる |
| `XY_AFTER_HOMING` / `Z_AFTER_HOMING` / `HOMING_BACKOFF_POST_MM` | ホーム後に勝手に動くと原点確認がしにくい |
| `QUICK_HOME`、カスタム起動画面・ステータス画面、`REVERSE_ENCODER_MENU_ITEM` 等の画面いじり | 精度に関係しない |
| `GRID_MAX_POINTS_X 3`（3 × 3） | 粗すぎる。5 × 5 に |
| E = 93、`INVERT_E0_DIR false` | 純正押出機の値。Sprite 用に 424.9 / true |
| 造形範囲 235 × 235 × 250 | 実測の 220 × 220 × 245 に |

## 原点出しと 1 層目のために入れたもの

| 設定 | 効果 |
|---|---|
| `USE_PROBE_FOR_Z_HOMING` + `Z_SAFE_HOMING` | Z 原点を BLTouch でベッド中央から取る |
| `MULTIPLE_PROBING 2` + 2 回目を 1/4 速度 | 2 回目をゆっくり当てて、原点のばらつきを減らす |
| `Z_MIN_PROBE_REPEATABILITY_TEST`（M48） | 原点の再現性を数値で確認できる |
| `RESTORE_LEVELING_AFTER_G28` | G28 の後もメッシュ補正が切れない |
| `G26_MESH_VALIDATION` | メッシュが合っているかを 1 層目のパターンで確認 |
| `PROBE_OFFSET_WIZARD` | Z オフセットを紙 1 枚で合わせるウィザード |
| `BABYSTEP_ZPROBE_OFFSET`（0.01 mm / クリック、ダブルクリックで呼び出し） | 印刷中の 1 層目調整がそのまま Z オフセットに保存される |
| `LCD_BED_TRAMMING` | 四隅のネジ調整を液晶から |
| `EEPROM_SETTINGS` + `EEPROM_AUTO_INIT` | オフセットとメッシュを保存。版が変わっても起動する |

## OctoPrint 連携

`HOST_ACTION_COMMANDS`、`HOST_PROMPT_SUPPORT`、`EMERGENCY_PARSER`、`ADVANCED_OK`、
`RX_BUFFER_SIZE 1024`、`LONG_FILENAME_HOST_SUPPORT`、`AUTO_REPORT_SD_STATUS` を有効化。
液晶での一時停止・中止や M600 のフィラメント交換を OctoPrint が認識できる。

## 実機で決める値（書き込み後に測る）

- [ ] BLTouch の X / Y オフセット（いまは仮の `-44, -10`）→ `M851 X.. Y..` → `M500`
- [ ] Z オフセット → 液晶の「プローブ Z オフセットウィザード」→ `M500`
- [ ] 各軸と押出の向き（逆なら `INVERT_*_DIR` を反転）
- [ ] 液晶が映るか（化けるなら `RET6_12864_LCD` → `VET6_12864_LCD`）
- [ ] PID（`M303 E0 S200 C8 U1`、`M303 E-1 S60 C8 U1`）→ `M500`
- [ ] E ステップの微調整（100 mm 押し出して実測）
- [ ] `M48 P10` で原点の再現性（目安：標準偏差 0.01 mm 前後）
