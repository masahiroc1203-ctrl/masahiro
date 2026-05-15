import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller bundle: exe の隣に uploads/ を作る
    EXE_DIR = Path(sys.executable).parent
    FRONTEND_DIST_DIR = Path(sys._MEIPASS) / "frontend_dist"
else:
    EXE_DIR = Path(__file__).parent
    FRONTEND_DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"

UPLOADS_DIR = EXE_DIR / "uploads"
