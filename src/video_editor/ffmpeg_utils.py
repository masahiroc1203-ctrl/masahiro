from __future__ import annotations

import shutil
import sys
from pathlib import Path


def find_ffmpeg() -> str:
    # PyInstaller bundle: <_MEIPASS>/ffmpeg/ffmpeg.exe
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "ffmpeg" / "ffmpeg.exe"  # type: ignore[attr-defined]
        if bundled.exists():
            return str(bundled)

    # Project-local: <repo_root>/ffmpeg/bin/ffmpeg[.exe]
    for candidate in [
        Path(__file__).parent.parent.parent / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path(__file__).parent.parent.parent / "ffmpeg" / "bin" / "ffmpeg",
        Path(__file__).parent.parent.parent / "ffmpeg" / "ffmpeg.exe",
        Path(__file__).parent.parent.parent / "ffmpeg" / "ffmpeg",
    ]:
        if candidate.exists():
            return str(candidate)

    # System PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    raise FileNotFoundError(
        "ffmpeg が見つかりません。\n"
        "https://ffmpeg.org/download.html からダウンロードしてPATHに追加するか、"
        "プロジェクトの ffmpeg/bin/ フォルダに配置してください。"
    )
