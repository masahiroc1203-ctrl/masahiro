from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import files, rename, content, merge, split

UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="PDF操作アプリ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(rename.router, prefix="/api/rename", tags=["rename"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(merge.router, prefix="/api/merge", tags=["merge"])
app.include_router(split.router, prefix="/api/split", tags=["split"])
