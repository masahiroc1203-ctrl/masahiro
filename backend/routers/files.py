import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

import config

UPLOADS_DIR = config.UPLOADS_DIR

router = APIRouter()


def safe_filename(filename: str) -> str:
    """ファイル名のパストラバーサルを防ぐ"""
    if os.sep in filename or (os.altsep and os.altsep in filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return filename


def unique_filename(directory: Path, filename: str) -> str:
    """同名ファイルがある場合は連番を付ける"""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = filename
    counter = 1
    while (directory / candidate).exists():
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


@router.post("/upload")
async def upload_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    filename = safe_filename(file.filename)

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    UPLOADS_DIR.mkdir(exist_ok=True)
    final_name = unique_filename(UPLOADS_DIR, filename)
    dest = UPLOADS_DIR / final_name

    content = await file.read()
    dest.write_bytes(content)

    return {"filename": final_name, "size": len(content)}


@router.get("")
async def list_files():
    UPLOADS_DIR.mkdir(exist_ok=True)
    result = []
    for path in sorted(UPLOADS_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            stat = path.stat()
            result.append(
                {
                    "filename": path.name,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
    return result


@router.delete("/all")
async def clear_all_files():
    """uploads/ 内の全 PDF ファイルを削除する"""
    UPLOADS_DIR.mkdir(exist_ok=True)
    deleted = []
    for path in UPLOADS_DIR.iterdir():
        if path.is_file() and path.suffix.lower() == ".pdf":
            path.unlink()
            deleted.append(path.name)
    return {"deleted_count": len(deleted), "deleted_files": deleted}


@router.get("/{filename}/download")
async def download_file(filename: str):
    filename = safe_filename(filename)
    path = UPLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename, media_type="application/pdf")
