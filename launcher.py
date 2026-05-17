"""
動画自動編集ツール エントリーポイント
ダブルクリックで起動 → uvicorn サーバー起動 → ブラウザ自動オープン
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _setup_paths() -> None:
    """PyInstaller バンドル内外で import パスと FFmpeg パスを解決する。"""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)          # PyInstaller 展開先
    else:
        base = Path(__file__).parent        # 通常実行時はプロジェクトルート

    # video_editor パッケージを import できるようにする
    src = base / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
    # バンドルされた video_editor/ を直接 import できる場合もあるため両方追加
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    # FFmpeg バイナリを PATH に追加（バンドル同梱 or ffmpeg/ フォルダ）
    for ffmpeg_dir in [base / "ffmpeg", Path(__file__).parent / "ffmpeg"]:
        if ffmpeg_dir.is_dir():
            os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ.get("PATH", "")
            break


def _start_server(port: int) -> None:
    import uvicorn
    from web.app import app
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def _open_browser(port: int, delay: float = 2.5) -> None:
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")


def main() -> None:
    _setup_paths()
    port = 8080

    print("=" * 45)
    print("  動画自動編集ツール")
    print("=" * 45)
    print(f"  起動中... http://localhost:{port}")
    print("  ブラウザが自動で開きます")
    print("  終了するにはこのウィンドウを閉じてください")
    print("=" * 45)

    threading.Thread(target=_start_server, args=(port,), daemon=True).start()
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n終了します。")


if __name__ == "__main__":
    multiprocessing.freeze_support()   # Windows で必須
    main()
