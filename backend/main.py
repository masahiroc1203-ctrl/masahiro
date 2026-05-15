import config

config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import content, files, merge, rename, split

app = FastAPI(title="PDF操作アプリ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(rename.router, prefix="/api/rename", tags=["rename"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(merge.router, prefix="/api/merge", tags=["merge"])
app.include_router(split.router, prefix="/api/split", tags=["split"])

# exe ビルド時またはフロントエンドビルドが存在する場合に静的ファイルを配信
if config.FRONTEND_DIST_DIR.exists():
    _assets = config.FRONTEND_DIST_DIR / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(str(config.FRONTEND_DIST_DIR / "index.html"))
