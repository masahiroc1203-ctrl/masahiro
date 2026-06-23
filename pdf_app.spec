# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "backend" / "app_launcher.py")],
    pathex=[str(ROOT / "backend")],
    binaries=[],
    datas=[
        (str(ROOT / "frontend" / "dist"), "frontend_dist"),
    ],
    hiddenimports=[
        # uvicorn internals
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.off",
        "uvicorn.lifespan.on",
        # pdfminer (pdfplumber の依存)
        "pdfminer",
        "pdfminer.high_level",
        "pdfminer.layout",
        "pdfminer.pdfpage",
        "pdfminer.pdfinterp",
        "pdfminer.pdfdevice",
        "pdfminer.pdfdocument",
        "pdfminer.pdfparser",
        "pdfminer.utils",
        "pdfminer.converter",
        "pdfminer.cmapdb",
        "pdfminer.image",
        "pdfminer.pdfcolor",
        # その他
        "anyio",
        "anyio.abc",
        "anyio._backends._asyncio",
        "email.mime.text",
        "email.mime.multipart",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pdf_app",
    debug=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
