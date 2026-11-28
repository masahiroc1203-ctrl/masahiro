#!/usr/bin/env python3
"""
Ender-3 Pro (Creality 4.2.7 + Sprite Extruder Pro + BLTouch + UBL) 用の
Marlin 設定を、公式 Marlin 2.1.3 の素の Configuration.h / Configuration_adv.h から生成する。

使い方:
    python3 apply_config.py <Marlin-2.1.3 の Marlin/ フォルダ> <出力フォルダ>

方針:
  - 素の公式設定に「このハードで必要な変更」だけを当てる。変更点はすべて下の CHANGES にある。
  - 元の行が見つからない、または複数見つかった場合はエラーで止める（黙って外れない）。
"""
import re
import sys
from pathlib import Path

# 操作:
#   ("set", 名前, 値)          #define を有効にして値を設定（コメントアウトされていても有効化）
#   ("on", 名前)               値なしの #define を有効化
#   ("off", 名前)              #define をコメントアウト
#   ("add_after", 名前, 行)     名前の #define 行の直後に1行追加
# 5番目の要素 after= を付けると、その文字列が現れた以降で最初に見つかった行を対象にする
# （GRID_MAX_POINTS_X のように同名が複数ある場合用）。

CONFIG = [
    # --- 機体・通信 ---
    ("set", "STRING_CONFIG_H_AUTHOR", '"(masahiro, Ender-3 Pro Sprite BLTouch)"'),
    ("set", "MOTHERBOARD", "BOARD_CREALITY_V427"),          # 4.2.7 基板
    ("set", "SERIAL_PORT", "1"),                             # 4.2.7 の USB(CH340) は USART1
    ("set", "BAUDRATE", "115200"),                           # OctoPrint が 115200 で接続実績あり
    ("set", "CUSTOM_MACHINE_NAME", '"Ender-3 Pro Sprite"'),

    # --- ドライバ（4.2.7 = TMC2208 スタンドアロン）---
    ("set", "X_DRIVER_TYPE", "TMC2208_STANDALONE"),
    ("set", "Y_DRIVER_TYPE", "TMC2208_STANDALONE"),
    ("set", "Z_DRIVER_TYPE", "TMC2208_STANDALONE"),
    ("set", "E0_DRIVER_TYPE", "TMC2208_STANDALONE"),

    # --- 温度 ---
    ("set", "BED_MAXTEMP", "125"),
    ("set", "DEFAULT_KP", "21.73"),                          # Creality の初期値。M303 で取り直す
    ("set", "DEFAULT_KI", "1.54"),
    ("set", "DEFAULT_KD", "76.55"),
    ("on", "PID_EDIT_MENU"),
    ("on", "PID_AUTOTUNE_MENU"),
    ("set", "TEMP_BED_WINDOW", "2"),
    ("set", "TEMP_BED_RESIDENCY_TIME", "5"),

    # --- モーション ---
    ("set", "DEFAULT_AXIS_STEPS_PER_UNIT", "{ 80, 80, 400, 424.9 }"),   # E は Sprite Extruder Pro
    ("set", "DEFAULT_MAX_FEEDRATE", "{ 300, 300, 5, 60 }"),
    ("set", "DEFAULT_MAX_ACCELERATION", "{ 1000, 1000, 100, 5000 }"),
    ("set", "DEFAULT_ACCELERATION", "500"),
    ("set", "DEFAULT_RETRACT_ACCELERATION", "1000"),
    ("set", "DEFAULT_TRAVEL_ACCELERATION", "1000"),
    ("set", "JUNCTION_DEVIATION_MM", "0.08"),
    ("set", "INVERT_Y_DIR", "false"),                        # 4.2.7 の配線向き
    ("set", "INVERT_Z_DIR", "true"),
    ("set", "INVERT_E0_DIR", "true"),                        # Sprite はダイレクトで逆回転（実機確認）
    ("set", "HOMING_FEEDRATE_MM_M", "{ (40*60), (40*60), (6*60) }"),
    ("on", "NO_MOTION_BEFORE_HOMING"),
    ("on", "HOME_AFTER_DEACTIVATE"),                         # モーター解放後は原点を取り直させる

    # --- 造形範囲（実測 220 x 220 x 245）---
    ("set", "X_BED_SIZE", "220"),
    ("set", "Y_BED_SIZE", "220"),
    ("set", "Z_MAX_POS", "245"),

    # --- BLTouch / Z 原点 ---
    ("off", "Z_MIN_PROBE_USES_Z_MIN_ENDSTOP_PIN"),           # BLTouch は専用ピン PB1
    ("on", "USE_PROBE_FOR_Z_HOMING"),
    ("on", "BLTOUCH"),
    ("set", "NOZZLE_TO_PROBE_OFFSET", "{ -44, -10, 0 }"),    # 仮。実測後に M851 で上書き→M500
    ("set", "PROBING_MARGIN", "10"),
    ("set", "Z_PROBE_FEEDRATE_SLOW", "(Z_PROBE_FEEDRATE_FAST / 4)"),  # 2回目をゆっくり当てて再現性を上げる
    ("set", "MULTIPLE_PROBING", "2"),
    ("set", "Z_CLEARANCE_DEPLOY_PROBE", "5"),
    ("set", "Z_CLEARANCE_BETWEEN_PROBES", "3"),
    ("set", "Z_CLEARANCE_MULTI_PROBE", "2"),
    ("set", "Z_PROBE_LOW_POINT", "-3"),
    ("set", "PROBE_OFFSET_ZMIN", "-5"),
    ("set", "PROBE_OFFSET_ZMAX", "5"),
    ("on", "Z_MIN_PROBE_REPEATABILITY_TEST"),                # M48 で原点の再現性を数値で確認
    ("on", "Z_SAFE_HOMING"),                                 # Z はベッド中央でプローブ

    # --- UBL ---
    ("on", "AUTO_BED_LEVELING_UBL"),
    ("on", "RESTORE_LEVELING_AFTER_G28"),
    ("on", "G26_MESH_VALIDATION"),                           # 1層目のメッシュ確認用パターン
    ("set", "MESH_TEST_HOTEND_TEMP", "200"),
    ("set", "MESH_TEST_BED_TEMP", "60"),
    ("set", "GRID_MAX_POINTS_X", "5", "#elif ENABLED(AUTO_BED_LEVELING_UBL)"),
    ("set", "MESH_INSET", "10", "#elif ENABLED(AUTO_BED_LEVELING_UBL)"),
    ("on", "UBL_HILBERT_CURVE"),
    ("on", "UBL_MESH_WIZARD"),
    ("on", "LCD_BED_LEVELING"),
    ("on", "MESH_EDIT_MENU"),
    ("on", "LCD_BED_TRAMMING"),                              # 四隅のネジ調整補助

    # --- 保存・画面・SD ---
    ("on", "EEPROM_SETTINGS"),
    ("on", "EEPROM_AUTO_INIT"),                              # 版が変わっても初期化して起動
    ("on", "NOZZLE_PARK_FEATURE"),
    ("set", "PREHEAT_1_LABEL", '"PLA"'),
    ("set", "PREHEAT_1_TEMP_HOTEND", "200"),
    ("set", "PREHEAT_1_TEMP_BED", "60"),
    ("set", "PREHEAT_2_LABEL", '"PETG"'),
    ("set", "PREHEAT_2_TEMP_HOTEND", "235"),
    ("set", "PREHEAT_2_TEMP_BED", "80"),
    ("on", "SDSUPPORT"),
    ("on", "SD_CHECK_AND_RETRY"),
    ("set", "ENCODER_STEPS_PER_MENU_ITEM", "2"),             # 以前の設定と同じノブの送り
    ("on", "ENCODER_NOISE_FILTER"),
    ("on", "CR10_STOCKDISPLAY"),
    ("add_after", "CR10_STOCKDISPLAY",
     "  #define RET6_12864_LCD   // 4.2.7 は多くが RET6。画面が映らない/化けるなら VET6_12864_LCD"),
    ("on", "SPEAKER"),
    ("on", "FAN_SOFT_PWM"),
]

CONFIG_ADV = [
    # --- OctoPrint 連携 ---
    ("on", "EMERGENCY_PARSER"),                              # M112/M108 を即時処理
    ("on", "ADVANCED_OK"),
    ("set", "RX_BUFFER_SIZE", "1024"),
    ("on", "HOST_ACTION_COMMANDS"),                          # 液晶での一時停止/中止を OctoPrint に通知
    ("on", "HOST_PROMPT_SUPPORT"),
    ("on", "LONG_FILENAME_HOST_SUPPORT"),
    ("on", "AUTO_REPORT_SD_STATUS"),
    ("on", "SCROLL_LONG_FILENAMES"),

    # --- 1層目のライブ調整 ---
    ("on", "BABYSTEPPING"),
    ("on", "BABYSTEP_ALWAYS_AVAILABLE"),
    ("on", "BABYSTEP_MILLIMETER_UNITS"),
    ("set", "BABYSTEP_MULTIPLICATOR_Z", "0.01"),             # 1クリック 0.01mm
    ("on", "DOUBLECLICK_FOR_Z_BABYSTEPPING"),
    ("on", "BABYSTEP_DISPLAY_TOTAL"),
    ("on", "BABYSTEP_ZPROBE_OFFSET"),                        # ベビーステップをそのまま Z オフセットに反映
    ("on", "PROBE_OFFSET_WIZARD"),
    ("set", "PROBE_OFFSET_WIZARD_START_Z", "-1.0"),

    # --- 一時停止・フィラメント交換（M600）---
    ("on", "ADVANCED_PAUSE_FEATURE"),
    ("on", "PARK_HEAD_ON_PAUSE"),
    ("on", "FILAMENT_LOAD_UNLOAD_GCODES"),
    ("set", "FILAMENT_CHANGE_UNLOAD_LENGTH", "80"),          # ダイレクトドライブなので短く
    ("set", "FILAMENT_CHANGE_FAST_LOAD_LENGTH", "40"),
]

DEFINE_RE = r"^(?P<indent>\s*)(?P<comment>//\s*)?#define\s+{name}\b(?P<rest>.*)$"


def find_line(lines, name, after=None):
    start = 0
    if after is not None:
        idx = [i for i, l in enumerate(lines) if after in l]
        if not idx:
            raise SystemExit(f"marker not found: {after!r}")
        start = idx[0]
    pat = re.compile(DEFINE_RE.format(name=re.escape(name)))
    hits = [i for i in range(start, len(lines)) if pat.match(lines[i])]
    if not hits:
        raise SystemExit(f"define not found: {name}")
    if after is None and len(hits) > 1:
        raise SystemExit(f"define {name} appears {len(hits)} times; give an after= marker")
    return hits[0], pat.match(lines[hits[0]])


def split_comment(rest):
    # rest = " value  // comment" -> (value, comment)
    m = re.match(r"^(?P<val>.*?)(?P<cm>\s*//.*)?$", rest)
    return m.group("val").strip(), (m.group("cm") or "")


def apply(path_in, path_out, changes):
    lines = Path(path_in).read_text(encoding="utf-8").split("\n")
    for ch in changes:
        op, name = ch[0], ch[1]
        after = ch[3] if len(ch) > 3 else None
        i, m = find_line(lines, name, after)
        indent = m.group("indent")
        val, cm = split_comment(m.group("rest"))
        if op == "set":
            lines[i] = f"{indent}#define {name} {ch[2]}{cm}"
        elif op == "on":
            lines[i] = f"{indent}#define {name}" + (f" {val}" if val else "") + cm
        elif op == "off":
            lines[i] = f"{indent}//#define {name}" + (f" {val}" if val else "") + cm
        elif op == "add_after":
            lines.insert(i + 1, ch[2])
        else:
            raise SystemExit(f"unknown op {op}")
    Path(path_out).write_text("\n".join(lines), encoding="utf-8")


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    apply(src / "Configuration.h", out / "Configuration.h", CONFIG)
    apply(src / "Configuration_adv.h", out / "Configuration_adv.h", CONFIG_ADV)
    print(f"wrote {out}/Configuration.h ({len(CONFIG)} changes), Configuration_adv.h ({len(CONFIG_ADV)} changes)")


if __name__ == "__main__":
    main()
