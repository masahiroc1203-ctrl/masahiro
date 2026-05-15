import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.pdf_extractor import extract_hinmei

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"

router = APIRouter()


def safe_filename(filename: str) -> str:
    """ファイル名のパストラバーサルを防ぐ"""
    if os.sep in filename or (os.altsep and os.altsep in filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return filename


class RenameRequest(BaseModel):
    new_filename: str


@router.get("/{filename}/preview")
async def preview_rename(filename: str):
    filename = safe_filename(filename)
    path = UPLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        hinmei = extract_hinmei(str(path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract hinmei: {str(e)}")

    if hinmei is None:
        return {
            "original_filename": filename,
            "hinmei": None,
            "suggested_filename": None,
        }

    stem = Path(filename).stem
    suggested = f"{stem}_{hinmei}.pdf"
    return {
        "original_filename": filename,
        "hinmei": hinmei,
        "suggested_filename": suggested,
    }


@router.post("/{filename}")
async def rename_file(filename: str, body: RenameRequest):
    filename = safe_filename(filename)
    new_filename = safe_filename(body.new_filename)

    if not new_filename:
        raise HTTPException(status_code=400, detail="new_filename must not be empty")

    if not new_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="new_filename must have .pdf extension")

    src = UPLOADS_DIR / filename
    if not src.exists() or not src.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    dst = UPLOADS_DIR / new_filename
    if dst.exists():
        raise HTTPException(status_code=400, detail="A file with the new name already exists")

    src.rename(dst)
    return {"old_filename": filename, "new_filename": new_filename}
