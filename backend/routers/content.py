import os
from pathlib import Path

import pdfplumber
from fastapi import APIRouter, HTTPException

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


@router.get("/{filename}/text")
async def get_text(filename: str):
    filename = safe_filename(filename)
    path = UPLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with pdfplumber.open(str(path)) as pdf:
            total_pages = len(pdf.pages)
            pages = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages.append({"page_num": i + 1, "text": text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")

    return {
        "filename": filename,
        "total_pages": total_pages,
        "pages": pages,
    }
