# 詳細設計: シーケンス図・フロー図

## メイン処理フロー（run コマンド）

```
User/CLI         Pipeline         VideoLoader     CycleDetector   SegmentExtractor   NumberingOverlay   VideoConcat
   │                │                  │                │                │                  │                │
   │─── run() ─────>│                  │                │                │                  │                │
   │                │── load() ────────>│                │                │                  │                │
   │                │<── VideoInfo ─────│                │                │                  │                │
   │                │                  │                │                │                  │                │
   │                │── get_frame(ref) ─>│               │                │                  │                │
   │                │<── frame ─────────│               │                │                  │                │
   │                │                  │                │                │                  │                │
   │                │── set_reference_frame(frame) ────>│                │                  │                │
   │                │                  │                │                │                  │                │
   │                │── detect_cycles(loader, video) ──>│                │                  │                │
   │                │                  │<─ iter_frames ─│                │                  │                │
   │                │                  │─ frames ──────>│                │                  │                │
   │                │                  │                │(compute sims)  │                  │                │
   │                │                  │                │(find peaks)    │                  │                │
   │                │<── List[CycleBoundary] ───────────│                │                  │                │
   │                │                  │                │                │                  │                │
   │                │── extract_all(boundaries, video) ─────────────────>│                  │                │
   │                │                  │<──────── FFmpeg subprocess ─────│                  │                │
   │                │<── List[Segment] ──────────────────────────────────│                  │                │
   │                │                  │                │                │                  │                │
   │                │── apply_all(segments) ─────────────────────────────────────────────>│                │
   │                │                  │                │                │        (OpenCV text render)      │
   │                │<── List[Segment] ──────────────────────────────────────────────────│                │
   │                │                  │                │                │                  │                │
   │                │── concat(segments, output_path) ─────────────────────────────────────────────────>│
   │                │                  │                │                │         (FFmpeg concat demuxer)  │
   │                │<── Path ──────────────────────────────────────────────────────────────────────────│
   │                │                  │                │                │                  │                │
   │                │── cleanup_temp() ──────────────────────────────────────────────────────────────────>│
   │<── ProcessingResult ─│            │                │                │                  │                │
```

---

## サイクル検出の詳細フロー

```
detect_cycles()
     │
     ├─ [stride スキャン]
     │    for i = 0, stride, 2*stride, ... total_frames:
     │         frame = loader.get_frame(i)
     │         sim[i] = compute_similarity(frame)
     │         ▲ 進捗コールバック
     │
     ├─ [ピーク検出]
     │    peaks = scipy.find_peaks(
     │              sim,
     │              height = threshold,
     │              distance = min_cycle_frames
     │            )
     │
     ├─ [ピーク精細化]
     │    for peak in peaks:
     │         window_start = max(0, peak - refine_window)
     │         window_end   = min(total, peak + refine_window)
     │         refined = window_start + argmax(sim[window_start:window_end])
     │
     ├─ [境界構築]
     │    boundaries = []
     │    for i, start in enumerate(refined):
     │         end = refined[i+1] - 1  (最後は total_frames - 1)
     │         boundaries.append(CycleBoundary(...))
     │
     └─ [バリデーション]
          if len(boundaries) == 0:
               raise CycleDetectionError
          return boundaries
```

---

## 区間切り出しの詳細フロー

```
extract(boundary, video)
     │
     ├─ [オフセット計算]
     │    cut_start = boundary.start_sec + start_offset_sec
     │    cut_end   = boundary.start_sec + end_offset_sec
     │
     ├─ [バリデーション]
     │    if cut_end > boundary.end_sec:
     │         log warning, return None
     │    if cut_start < 0:
     │         cut_start = 0
     │
     ├─ [一時ファイルパス生成]
     │    clip_path = temp_dir / f"clip_{boundary.cycle_id:03d}.mp4"
     │
     ├─ [FFmpeg実行]
     │    cmd = [
     │      "ffmpeg", "-i", video.path,
     │      "-ss", str(cut_start),
     │      "-to", str(cut_end),
     │      "-c:v", codec,
     │      "-b:v", bitrate,
     │      "-an",          # 音声なし
     │      "-y", clip_path
     │    ]
     │    subprocess.run(cmd, check=True, capture_output=True)
     │
     └─ return Segment(...)
```

---

## エラーハンドリングフロー

```
Pipeline.run()
     │
     ├─ try:
     │    VideoLoader.load()
     │    ├─ OSError → VideoLoadError("ファイルが開けません")
     │    └─ cv2 error → VideoLoadError("コーデックエラー")
     │
     │    CycleDetector.detect_cycles()
     │    ├─ 検出0件 → CycleDetectionError
     │    │    → ユーザーへ: "閾値を下げてみてください"
     │    └─ OK
     │
     │    SegmentExtractor.extract_all()
     │    ├─ 一部スキップ → WARNING ログ + ProcessingResult.skipped_cycles に記録
     │    ├─ FFmpeg失敗 → SegmentExtractionError
     │    └─ OK
     │
     │    NumberingOverlay.apply_all()
     │    ├─ cv2 失敗 → OverlayError
     │    └─ OK
     │
     │    VideoConcat.concat()
     │    ├─ FFmpeg失敗 → ConcatError
     │    └─ OK
     │
     └─ finally:
          cleanup_temp()  ← エラー時も一時ファイルを削除
```

---

## 類似度グラフのイメージ（preview コマンド出力）

```
類似度
1.0 │      │         │         │         │         │
    │      ▲         ▲         ▲         ▲         ▲  ← ピーク (サイクル開始点)
0.9 │     ╱│╲       ╱│╲       ╱│╲       ╱│╲       ╱│╲
    │    ╱ │ ╲     ╱ │ ╲     ╱ │ ╲     ╱ │ ╲     ╱ │ ╲
0.5 │   ╱  │  ╲   ╱  │  ╲   ╱  │  ╲   ╱  │  ╲   ╱  │  ╲
    │  ╱   │   ╲_╱   │   ╲_╱   │   ╲_╱   │   ╲_╱   │   ╲
0.0 │──────┼─────────┼─────────┼─────────┼─────────┼────▶ 時刻(秒)
    0      5        10        15        20        25
         ↑基準フレーム #150 = 5.0秒
    [threshold=0.92 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─]
```

---

## ディレクトリ構成（完成形）

```
masahiro/
├── src/
│   └── video_editor/
│       ├── __init__.py
│       ├── models.py           # VideoInfo, CycleBoundary, Segment, ProcessingResult
│       ├── config.py           # AppConfig と全サブ設定 (Pydantic)
│       ├── exceptions.py       # カスタム例外
│       ├── loader.py           # VideoLoader
│       ├── cycle_detector.py   # CycleDetector
│       ├── extractor.py        # SegmentExtractor
│       ├── overlay.py          # NumberingOverlay
│       ├── concat.py           # VideoConcat
│       └── pipeline.py         # VideoEditingPipeline
├── src/
│   └── cli.py                  # Typer CLI エントリーポイント
├── tests/
│   ├── conftest.py             # pytest フィクスチャ (テスト動画生成等)
│   ├── fixtures/
│   │   └── create_test_video.py
│   ├── unit/
│   │   ├── test_loader.py
│   │   ├── test_cycle_detector.py
│   │   ├── test_extractor.py
│   │   ├── test_overlay.py
│   │   └── test_concat.py
│   └── integration/
│       ├── test_pipeline.py
│       └── test_cli.py
├── docs/
│   ├── 01_data_models.md
│   ├── 02_module_api.md
│   ├── 03_cli_and_config.md
│   ├── 04_test_plan.md
│   └── 05_sequence_diagram.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── Dockerfile
└── DESIGN.md                   # 概要設計（工程表）
```

---

## requirements.txt（予定）

```
# 動画処理
opencv-python>=4.9.0
ffmpeg-python>=0.2.0

# 数値計算
numpy>=1.26.0
scipy>=1.12.0

# 設定管理
pydantic>=2.6.0
pyyaml>=6.0.1

# CLI
typer[all]>=0.12.0

# 画像処理（オーバーレイ補助）
Pillow>=10.3.0
```

```
# requirements-dev.txt
pytest>=8.0.0
pytest-cov>=5.0.0
pytest-mock>=3.12.0
```
