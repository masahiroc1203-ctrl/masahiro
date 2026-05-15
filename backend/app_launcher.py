"""PyInstaller 用エントリポイント。uvicorn を起動してブラウザを開く。"""
import threading
import time
import webbrowser

import config

config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

import uvicorn
from main import app


def _open_browser():
    time.sleep(2.0)
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    print("PDF操作アプリを起動しています...")
    print(f"ファイル保存先: {config.UPLOADS_DIR}")
    print("ブラウザが自動で開きます。手動の場合: http://localhost:8000")
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
