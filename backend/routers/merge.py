import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter

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


class MergeRequest(BaseModel):
    filenames: list[str]
    output_filename: str


@router.post("")
async def merge_files(body: MergeRequest):
    if len(body.filenames) < 2:
        raise HTTPException(status_code=400, detail="At least 2 files are required for merging")

    output_filename = body.output_filename.strip()
    if not output_filename:
        raise HTTPException(status_code=400, detail="output_filename must not be empty")
    if not output_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="output_filename must end with .pdf")
    if "/" in output_filename or "\\" in output_filename or os.sep in output_filename:
        raise HTTPException(status_code=400, detail="output_filename must not contain directory separators")

    for fname in body.filenames:
        safe = safe_filename(fname)
        fpath = UPLOADS_DIR / safe
        if not fpath.exists() or not fpath.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {fname}")

    writer = PdfWriter()
    merged_count = 0
    for fname in body.filenames:
        safe = safe_filename(fname)
        fpath = UPLOADS_DIR / safe
        reader = PdfReader(str(fpath))
        for page in reader.pages:
            writer.add_page(page)
        merged_count += 1

    UPLOADS_DIR.mkdir(exist_ok=True)
    final_name = unique_filename(UPLOADS_DIR, output_filename)
    out_path = UPLOADS_DIR / final_name

    with open(str(out_path), "wb") as f:
        writer.write(f)

    return {"output_filename": final_name, "merged_count": merged_count}
