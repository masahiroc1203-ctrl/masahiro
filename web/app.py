from __future__ import annotations

import shutil
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 通常実行時のみ src/ を追加（PyInstaller バンドル内では launcher.py が解決済み）
if not getattr(sys, "frozen", False):
    _src = Path(__file__).parent.parent / "src"
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

import cv2
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
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

MAX_UPLOAD_BYTES = 4 * 1024 ** 3  # 4 GB

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})

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
_uploads: Dict[str, Dict[str, Any]] = {}
_jobs: Dict[str, Dict[str, Any]] = {}

# ------------------------------------------------------------------ #
# ルーティング
# ------------------------------------------------------------------ #


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=_HTML)


# ---- Step 1: 複数動画アップロード ----

@app.post("/api/upload")
async def upload_videos(
    videos: List[UploadFile] = File(...),
) -> dict:
    upload_id = uuid.uuid4().hex[:8]
    upload_dir = UPLOAD_DIR / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved: List[str] = []
    for video in videos:
        safe_name = Path(video.filename or "video.mp4").name
        dest = upload_dir / safe_name
        with open(dest, "wb") as f:
            shutil.copyfileobj(video.file, f)
        saved.append(safe_name)

    # ファイル名の自然順ソート
    import re
    def _key(s: str) -> list:
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]

    saved.sort(key=_key)
    _uploads[upload_id] = {"dir": str(upload_dir), "files": saved}

    return {"upload_id": upload_id, "files": saved}


# ---- Step 2: 基準フレームプレビュー ----

@app.get("/api/frame/{upload_id}")
async def get_frame(upload_id: str, time_sec: float = 0.0) -> Response:
    if upload_id not in _uploads:
        raise HTTPException(status_code=404, detail="upload_id が見つかりません")

    upload = _uploads[upload_id]
    if not upload["files"]:
        raise HTTPException(status_code=400, detail="ファイルがありません")

    # 先頭ファイルからフレームを取得
    video_path = Path(upload["dir"]) / upload["files"][0]
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_num = min(int(time_sec * fps), max(0, total - 1))

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise HTTPException(status_code=400, detail="フレームを取得できませんでした")

    # サムネイルサイズにリサイズ（幅320px）
    h, w = frame.shape[:2]
    thumb_w = 320
    thumb_h = int(h * thumb_w / w)
    thumb = cv2.resize(frame, (thumb_w, thumb_h))

    _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(content=buf.tobytes(), media_type="image/jpeg")


# ---- Step 3: 処理開始 ----

@app.post("/api/process/{upload_id}")
async def process_videos(
    upload_id: str,
    background_tasks: BackgroundTasks,
    ref_time_sec: float = Form(...),
    before_sec: float = Form(0.0),
    after_sec: float = Form(5.0),
    threshold: float = Form(0.92),
    min_cycle_sec: float = Form(5.0),
    overlay_text: str = Form("Cycle {n}"),
    roi_x: float = Form(0.0),
    roi_y: float = Form(0.0),
    roi_w: float = Form(1.0),
    roi_h: float = Form(1.0),
) -> dict:
    if upload_id not in _uploads:
        raise HTTPException(status_code=404, detail="upload_id が見つかりません")

    job_id = uuid.uuid4().hex[:8]
    output_path = OUTPUT_DIR / f"{job_id}_output.mp4"

    _jobs[job_id] = {
        "status": "processing",
        "stage": "待機中",
        "progress": 0,
        "result": None,
        "error": None,
    }

    upload = _uploads[upload_id]
    video_paths = [Path(upload["dir"]) / f for f in upload["files"]]

    roi = (roi_x, roi_y, roi_w, roi_h) if (roi_w < 0.999 or roi_h < 0.999) else None

    background_tasks.add_task(
        _run_pipeline,
        job_id, video_paths, output_path,
        ref_time_sec, before_sec, after_sec,
        threshold, min_cycle_sec, overlay_text, roi,
    )
    return {"job_id": job_id}


# ---- ポーリング ----

@app.get("/api/status/{job_id}")
async def get_status(job_id: str) -> dict:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return _jobs[job_id]


# ---- ダウンロード ----

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
    return FileResponse(str(output_path), media_type="video/mp4", filename="output.mp4")


# ------------------------------------------------------------------ #
# バックグラウンド処理
# ------------------------------------------------------------------ #


def _run_pipeline(
    job_id: str,
    video_paths: list,
    output_path: Path,
    ref_time_sec: float,
    before_sec: float,
    after_sec: float,
    threshold: float,
    min_cycle_sec: float,
    overlay_text: str,
    roi: tuple | None = None,
) -> None:
    def on_progress(stage: str, pct: float) -> None:
        _jobs[job_id]["stage"] = stage
        _jobs[job_id]["progress"] = round(pct * 100)

    try:
        config = AppConfig(
            input=InputConfig(
                video_path=video_paths[0],
                reference_time_sec=ref_time_sec,
            ),
            cycle=CycleConfig(
                similarity_threshold=threshold,
                min_cycle_sec=min_cycle_sec,
                roi=roi,
            ),
            extraction=ExtractionConfig(
                before_sec=before_sec,
                after_sec=after_sec,
            ),
            overlay=OverlayConfig(text_template=overlay_text),
            output=OutputConfig(
                video_path=output_path,
                temp_dir=UPLOAD_DIR / f"{job_id}_tmp",
            ),
        )
        pipeline = VideoEditingPipeline(config)
        result = pipeline.run_multi(video_paths, output_path, on_progress)

        _jobs[job_id].update({
            "status": "done",
            "stage": "完了",
            "progress": 100,
            "result": {
                "detected_cycles": result.detected_cycles,
                "extracted_segments": result.extracted_segments,
                "skipped_cycles": result.skipped_cycles,
                "processing_time_sec": round(result.processing_time_sec, 1),
            },
        })
    except (VideoEditorError, Exception) as e:
        _jobs[job_id].update({
            "status": "error",
            "stage": "エラー",
            "error": str(e),
        })
