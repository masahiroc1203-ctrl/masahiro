from __future__ import annotations

import shutil
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

# 通常実行時のみ src/ を追加（PyInstaller バンドル内では launcher.py が解決済み）
if not getattr(sys, "frozen", False):
    _src = Path(__file__).parent.parent / "src"
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from video_editor.config import (
    AppConfig,
    CycleConfig,
    ExtractionConfig,
    InputConfig,
    OutputConfig,
    OverlayConfig,
)
from video_editor.exceptions import VideoEditorError
from video_editor.pipeline import VideoEditingPipeline

# ------------------------------------------------------------------ #
# アプリ設定
# ------------------------------------------------------------------ #

app = FastAPI(title="動画自動編集ツール", docs_url=None, redoc_url=None)

BASE_DIR = Path(__file__).parent
_STATIC = BASE_DIR / "static"
if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

_HTML = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")

UPLOAD_DIR = Path("./uploads")
OUTPUT_DIR = Path("./outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

_executor = ThreadPoolExecutor(max_workers=2)
_jobs: Dict[str, Dict[str, Any]] = {}

# ------------------------------------------------------------------ #
# ルーティング
# ------------------------------------------------------------------ #


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=_HTML)


@app.post("/api/process")
async def process_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(..., description="入力動画ファイル"),
    ref_frame: int = Form(..., description="基準フレーム番号"),
    start_offset: float = Form(0.0, description="切り出し開始オフセット（秒）"),
    end_offset: float = Form(5.0, description="切り出し終了オフセット（秒）"),
    threshold: float = Form(0.92, description="類似度閾値 0〜1"),
    overlay_text: str = Form("Cycle {n}", description="ナンバリングテキスト"),
) -> dict:
    job_id = uuid.uuid4().hex[:8]
    input_path = UPLOAD_DIR / f"{job_id}_{video.filename}"
    output_path = OUTPUT_DIR / f"{job_id}_output.mp4"

    with open(input_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    _jobs[job_id] = {
        "status": "processing",
        "stage": "待機中",
        "progress": 0.0,
        "result": None,
        "error": None,
        "filename": video.filename,
    }

    background_tasks.add_task(
        _run_pipeline,
        job_id,
        input_path,
        output_path,
        ref_frame,
        start_offset,
        end_offset,
        threshold,
        overlay_text,
    )

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> dict:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return _jobs[job_id]


@app.get("/api/download/{job_id}")
async def download(job_id: str) -> FileResponse:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    job = _jobs[job_id]
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="処理がまだ完了していません")
    output_path = OUTPUT_DIR / f"{job_id}_output.mp4"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="出力ファイルが見つかりません")
    return FileResponse(
        str(output_path),
        media_type="video/mp4",
        filename="output.mp4",
    )


# ------------------------------------------------------------------ #
# バックグラウンド処理
# ------------------------------------------------------------------ #


def _run_pipeline(
    job_id: str,
    input_path: Path,
    output_path: Path,
    ref_frame: int,
    start_offset: float,
    end_offset: float,
    threshold: float,
    overlay_text: str,
) -> None:
    def on_progress(stage: str, pct: float) -> None:
        _jobs[job_id]["stage"] = stage
        _jobs[job_id]["progress"] = round(pct * 100)

    try:
        config = AppConfig(
            input=InputConfig(video_path=input_path, reference_frame=ref_frame),
            cycle=CycleConfig(similarity_threshold=threshold),
            extraction=ExtractionConfig(
                start_offset_sec=start_offset,
                end_offset_sec=end_offset,
            ),
            overlay=OverlayConfig(text_template=overlay_text),
            output=OutputConfig(
                video_path=output_path,
                temp_dir=UPLOAD_DIR / f"{job_id}_tmp",
            ),
        )
        pipeline = VideoEditingPipeline(config)
        result = pipeline.run(progress_callback=on_progress)

        _jobs[job_id].update(
            {
                "status": "done",
                "stage": "完了",
                "progress": 100,
                "result": {
                    "detected_cycles": result.detected_cycles,
                    "extracted_segments": result.extracted_segments,
                    "skipped_cycles": result.skipped_cycles,
                    "processing_time_sec": round(result.processing_time_sec, 1),
                },
            }
        )
    except (VideoEditorError, Exception) as e:
        _jobs[job_id].update(
            {
                "status": "error",
                "stage": "エラー",
                "error": str(e),
            }
        )
    finally:
        if input_path.exists():
            input_path.unlink()
