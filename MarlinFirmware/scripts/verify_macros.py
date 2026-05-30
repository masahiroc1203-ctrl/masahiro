#!/usr/bin/env python3
"""
Marlin マクロ検証スクリプト
実際のビルドと同じフラグでプリプロセッサを走らせ、どの値が採用されたかを確認する。

使い方:
  python3 scripts/verify_macros.py
  ※ pio run の後に実行すること（compile_commands.json が必要）
"""
import sys
import os
import glob
import subprocess
import json
import tempfile

# 検証対象マクロ（名前, 説明）
MACROS = [
    # バージョン
    ("SHORT_BUILD_VERSION",           "LCDに表示されるバージョン文字列"),
    ("DETAILED_BUILD_VERSION",        "詳細バージョン文字列"),
    ("STRING_DISTRIBUTION_DATE",      "ビルド日付"),
    # ファン・ヒーター
    ("E0_AUTO_FAN_PIN",               "ホットエンド冷却ファン制御ピン（-1=無効）"),
    ("EXTRUDER_AUTO_FAN_TEMPERATURE", "ホットエンドファン起動温度(℃)"),
    ("FAN0_PIN",                      "パーツ冷却ファン"),
    ("HEATER_0_PIN",                  "ホットエンドヒーター"),
    ("HEATER_BED_PIN",                "ヒートベッド"),
    # 温度センサー
    ("TEMP_0_PIN",                    "ホットエンド温度センサー"),
    ("TEMP_BED_PIN",                  "ベッド温度センサー"),
    # プローブ
    ("SERVO0_PIN",                    "BLTouch OUT（制御信号）"),
    ("Z_MIN_PROBE_PIN",               "BLTouch IN（トリガー信号）"),
    # ステッパーピン
    ("X_STEP_PIN",                    "X軸ステップ"),
    ("Y_STEP_PIN",                    "Y軸ステップ"),
    ("Z_STEP_PIN",                    "Z軸ステップ"),
    ("E0_STEP_PIN",                   "エクストルーダーステップ"),
    ("X_ENABLE_PIN",                  "ステッパーENABLE（共通）"),
    # フィラメントセンサー
    ("FIL_RUNOUT_PIN",                "フィラメント切れセンサー"),
    # プローブオフセット・メッシュ
    ("PROBE_X_OFFSET",                "BLTouch XオフセットFromノズル(mm)"),
    ("PROBE_Y_OFFSET",                "BLTouch YオフセットFromノズル(mm)"),
    ("PROBE_Z_OFFSET",                "BLTouch Zトリガーオフセット(mm)"),
    ("GRID_MAX_POINTS_X",             "UBLメッシュグリッド数"),
    ("MESH_MIN_X",                    "メッシュ最小X(mm)"),
    ("MESH_MAX_X",                    "メッシュ最大X(mm)"),
    ("MESH_MIN_Y",                    "メッシュ最小Y(mm)"),
    ("MESH_MAX_Y",                    "メッシュ最大Y(mm)"),
    # フィラメント設定
    ("EXTRUDE_MAXLENGTH",             "最大押し出し長(mm)"),
    ("FILAMENT_CHANGE_UNLOAD_LENGTH", "フィラメントアンロード長(mm)"),
]


def find_arm_cpp():
    """PlatformIO のツールチェーンから arm-none-eabi-cpp を探す。"""
    home = os.path.expanduser("~")
    patterns = [
        f"{home}/.platformio/packages/toolchain-gccarmnoneeabi*/bin/arm-none-eabi-cpp",
        f"{home}/.platformio/packages/toolchain-gccarmnoneeabi/bin/arm-none-eabi-cpp",
    ]
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    return None


def load_compile_commands(build_dir, project_dir):
    """compile_commands.json から Marlin ソースのコンパイルフラグを抽出する。"""
    # PlatformIO は project root か build_dir に生成する
    candidates = [
        os.path.join(project_dir, "compile_commands.json"),
        os.path.join(build_dir, "compile_commands.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                commands = json.load(f)
            # MarlinCore を優先（全設定が include される中心ファイル）
            for cmd in commands:
                if "MarlinCore" in cmd.get("file", ""):
                    return cmd
            return commands[0] if commands else None
    return None


def extract_flags(cmd_entry):
    """compile_commands.json のエントリからプリプロセッサに必要なフラグを抽出する。"""
    command = cmd_entry.get("command", "")
    parts = command.split()
    if not parts:
        return None, [], "."

    cc = parts[0].replace("gcc", "cpp")  # gcc → cpp に変換
    src_dir = cmd_entry.get("directory", ".")

    flags = []
    i = 1
    while i < len(parts):
        p = parts[i]
        # インクルードパス・定義・コンパイラフラグを収集
        if p.startswith(("-I", "-D")):
            flags.append(p)
        elif p.startswith(("-m", "-f", "-std", "-O", "-g", "-W")):
            flags.append(p)
        elif p in ("-I", "-D", "-include", "-isystem"):
            flags.append(p)
            if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                i += 1
                flags.append(parts[i])
        i += 1

    return cc, flags, src_dir


def run_preprocessor(cpp, flags, src_dir, probe_path):
    """プリプロセッサを -dM -E モードで実行しマクロダンプを取得する。"""
    cmd = [cpp, "-dM", "-E"] + flags + [probe_path]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=src_dir)
    return result.stdout, result.stderr


def parse_macro_dump(dump_output):
    """#define 一覧をパースして dict に変換する。"""
    macros = {}
    for line in dump_output.splitlines():
        if line.startswith("#define "):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                name = parts[1]
                value = parts[2].strip() if len(parts) > 2 else "(defined)"
                macros[name] = value
    return macros


def format_report(macro_values):
    """検証結果をフォーマットした文字列を返す。"""
    lines = []
    lines.append("=" * 72)
    lines.append("  MARLIN MACRO VERIFICATION REPORT")
    lines.append("  ビルドで実際に採用された値の一覧")
    lines.append("=" * 72)
    lines.append(f"  {'マクロ名':<42} 採用値")
    lines.append("-" * 72)

    has_undefined = False
    for macro, description in MACROS:
        val = macro_values.get(macro)
        if val is None:
            display = "*** NOT DEFINED ***"
            prefix = "!"
            has_undefined = True
        else:
            # 長い値は切り詰める
            display = val if len(val) <= 28 else val[:25] + "..."
            prefix = " "
        lines.append(f"  {prefix} {macro:<40} {display}")
        lines.append(f"      └ {description}")

    lines.append("=" * 72)
    if has_undefined:
        lines.append("  ! = 未定義のマクロ（設定漏れの可能性あり）")
    lines.append("")
    return "\n".join(lines)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    build_dir = os.path.join(project_dir, ".pio", "build", "STM32F103RE_creality")
    report_path = os.path.join(build_dir, "macro_verify.txt")

    print("\n[verify_macros] Marlin マクロ検証を開始します...\n")

    # 1. arm-none-eabi-cpp を探す
    cpp = find_arm_cpp()
    if not cpp:
        print("ERROR: arm-none-eabi-cpp が見つかりません。")
        print("       'pio run' を先に実行してツールチェーンをインストールしてください。")
        sys.exit(1)
    print(f"  プリプロセッサ: {cpp}")

    # 2. compile_commands.json を読み込む
    cmd_entry = load_compile_commands(build_dir, project_dir)
    if cmd_entry is None:
        print(f"ERROR: compile_commands.json が見つかりません。")
        print(f"       'pio run -e STM32F103RE_creality -t compiledb' を実行してください。")
        sys.exit(1)

    cc, flags, src_dir = extract_flags(cmd_entry)
    print(f"  ソースディレクトリ: {src_dir}")
    print(f"  フラグ数: {len(flags)}")

    # 3. プローブファイルを作成（全設定が include される MarlinConfig.h を読み込む）
    probe_content = '#include "inc/MarlinConfig.h"\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
        f.write(probe_content)
        probe_path = f.name

    try:
        # 4. プリプロセッサ実行
        print("  プリプロセッサを実行中...", flush=True)
        dump_output, stderr = run_preprocessor(cpp, flags, src_dir, probe_path)

        if not dump_output.strip():
            print("ERROR: プリプロセッサ出力が空です。")
            if stderr:
                print(f"  STDERR: {stderr[:1000]}")
            sys.exit(1)

        # 5. マクロをパース
        macro_values = parse_macro_dump(dump_output)
        print(f"  マクロ定義数: {len(macro_values)}")
        print()

        # 6. レポート生成・表示
        report = format_report(macro_values)
        print(report)

        # 7. ファイルに保存
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(report)
        print(f"  レポート保存先: {report_path}")

    finally:
        os.unlink(probe_path)


if __name__ == "__main__":
    main()
