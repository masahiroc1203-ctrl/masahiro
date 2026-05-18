#!/usr/bin/env python3
"""Fiji を起動して batch_hsv_analysis.ijm を実行するランチャー。"""

import subprocess
import sys
from pathlib import Path

# OS 別の Fiji 実行ファイルの候補パス
FIJI_CANDIDATES = [
    # Linux
    Path("/opt/fiji/Fiji.app/ImageJ-linux64"),
    Path.home() / "Fiji.app/ImageJ-linux64",
    # macOS
    Path("/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"),
    Path.home() / "Applications/Fiji.app/Contents/MacOS/ImageJ-macosx",
    # Windows (WSL 経由では動作しない場合あり)
    Path("C:/Fiji.app/ImageJ-win64.exe"),
]


def find_fiji() -> Path | None:
    for p in FIJI_CANDIDATES:
        if p.exists():
            return p
    return None


def main() -> None:
    # config.yaml があれば fiji_path を読む
    config_path = Path(__file__).parent / "config.yaml"
    fiji_path: Path | None = None

    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            raw = cfg.get("fiji_path", "")
            if raw and raw != "/path/to/Fiji.app/ImageJ-linux64":
                fiji_path = Path(raw)
        except ImportError:
            pass  # pyyaml がない場合は自動検索にフォールバック

    if fiji_path is None or not fiji_path.exists():
        fiji_path = find_fiji()

    if fiji_path is None:
        print("Fiji が見つかりませんでした。")
        print("以下のいずれかを実施してください:")
        print("  1. config.yaml の fiji_path を正しいパスに設定する")
        print("  2. Fiji を標準の場所にインストールする")
        sys.exit(1)

    macro_path = Path(__file__).parent / "macros" / "batch_hsv_analysis.ijm"
    if not macro_path.exists():
        print(f"マクロファイルが見つかりません: {macro_path}")
        sys.exit(1)

    print(f"Fiji パス : {fiji_path}")
    print(f"マクロ    : {macro_path}")
    print("Fiji を起動します... (ダイアログに従って操作してください)")

    # GUI モードで起動（インタラクティブな ROI 設定が必要なため --headless 不可）
    subprocess.run([str(fiji_path), "--run", str(macro_path)], check=False)


if __name__ == "__main__":
    main()
