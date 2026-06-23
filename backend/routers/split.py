import os
from pathlib import Path
from typing import Literal

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


def write_pages(reader: PdfReader, page_indices: list[int], out_path: Path) -> None:
    """指定したページインデックス（0始まり）をファイルに書き出す"""
    writer = PdfWriter()
    for idx in page_indices:
        writer.add_page(reader.pages[idx])
    with open(str(out_path), "wb") as f:
        writer.write(f)


class SplitRequest(BaseModel):
    mode: Literal["ranges", "every"]
    ranges: list[list[int]] | None = None
    every: int | None = None


@router.post("/{filename}")
async def split_file(filename: str, body: SplitRequest):
    filename = safe_filename(filename)
    path = UPLOADS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    reader = PdfReader(str(path))
    total_pages = len(reader.pages)
    stem = Path(filename).stem

    output_files: list[str] = []

    if body.mode == "ranges":
        if not body.ranges:
            raise HTTPException(status_code=400, detail="ranges must be provided for mode 'ranges'")
        for rng in body.ranges:
            if len(rng) != 2:
                raise HTTPException(status_code=400, detail="Each range must have exactly 2 elements [start, end]")
            start, end = rng
            if start < 1 or end > total_pages or start > end:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid range [{start}, {end}] for PDF with {total_pages} pages",
                )
            indices = list(range(start - 1, end))
            if start == end:
                out_name = f"{stem}_p{start}.pdf"
            else:
                out_name = f"{stem}_p{start}-{end}.pdf"
            final_name = unique_filename(UPLOADS_DIR, out_name)
            write_pages(reader, indices, UPLOADS_DIR / final_name)
            output_files.append(final_name)

    elif body.mode == "every":
        if body.every is None or body.every < 1:
            raise HTTPException(status_code=400, detail="every must be a positive integer for mode 'every'")
        n = body.every
        start = 1
        while start <= total_pages:
            end = min(start + n - 1, total_pages)
            indices = list(range(start - 1, end))
            if start == end:
                out_name = f"{stem}_p{start}.pdf"
            else:
                out_name = f"{stem}_p{start}-{end}.pdf"
            final_name = unique_filename(UPLOADS_DIR, out_name)
            write_pages(reader, indices, UPLOADS_DIR / final_name)
            output_files.append(final_name)
            start += n

    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

    return {
        "original_filename": filename,
        "output_files": output_files,
        "split_count": len(output_files),
    }
