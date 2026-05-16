# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller スペックファイル
使い方: pyinstaller video_editor.spec
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ---- 動的収集 ----
datas    = []
binaries = []
hiddenimports = []

for pkg in ["uvicorn", "fastapi", "starlette", "anyio", "cv2"]:
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# Web テンプレート
datas += [("web/templates", "web/templates")]

# FFmpeg バイナリを同梱（ffmpeg/ フォルダが存在する場合）
if os.path.isdir("ffmpeg"):
    binaries += [("ffmpeg/*", "ffmpeg")]

# ---- Analysis ----
a = Analysis(
    ["launcher.py"],
    pathex=["src", "."],           # video_editor と web を両方 import 可能にする
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        # アプリ固有
        "video_editor",
        "video_editor.pipeline",
        "video_editor.loader",
        "video_editor.cycle_detector",
        "video_editor.extractor",
        "video_editor.overlay",
        "video_editor.concat",
        "video_editor.config",
        "video_editor.models",
        "video_editor.exceptions",
        "web",
        "web.app",
        # 数値計算
        "scipy",
        "scipy.signal",
        "scipy._lib",
        "scipy.special",
        "scipy.special._cdflib",
        # 設定・CLI
        "pydantic",
        "pydantic_core",
        "yaml",
        "typer",
        # Web
        "multipart",
        "aiofiles",
        "h11",
        "httptools",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="動画編集ツール",
    debug=False,
    strip=False,
    upx=True,
    console=True,          # コンソール表示あり（起動状態が確認できる）
    icon=None,             # icon.ico を用意した場合は "icon.ico" に変更
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="動画編集ツール",
)
