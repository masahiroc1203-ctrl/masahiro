"""PyInstaller 用エントリポイント。uvicorn を起動してブラウザを開く。"""
import multiprocessing
import sys
import threading
import time
import traceback
import webbrowser

# Windows の PyInstaller + multiprocessing に必要
multiprocessing.freeze_support()

try:
    import config
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    import uvicorn
    from main import app
except Exception:
    traceback.print_exc()
    print("\n--- 起動エラー ---")
    print("上記のエラーを確認してください。")
    input("Enterキーを押して終了...")
    sys.exit(1)


def _open_browser():
    time.sleep(2.0)
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    print("PDF操作アプリを起動しています...")
    print(f"ファイル保存先: {config.UPLOADS_DIR}")
    print("ブラウザが自動で開きます。手動の場合: http://localhost:8000")
    try:
        threading.Thread(target=_open_browser, daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except OSError as e:
        print(f"\n--- 起動エラー ---")
        print(f"ポート 8000 が既に使用中の可能性があります: {e}")
        print("タスクマネージャーで他のアプリが 8000 番ポートを使っていないか確認してください。")
        input("Enterキーを押して終了...")
        sys.exit(1)
    except Exception:
        traceback.print_exc()
        print("\n--- 予期しないエラー ---")
        input("Enterキーを押して終了...")
        sys.exit(1)
