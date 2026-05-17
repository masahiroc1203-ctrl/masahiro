# 詳細設計: データモデル

## クラス図

```
AppConfig
├── InputConfig
├── CycleConfig
├── ExtractionConfig
├── OverlayConfig
└── OutputConfig

VideoInfo                 ← VideoLoader が返す
CycleBoundary             ← CycleDetector が返す (1サイクル分)
Segment                   ← SegmentExtractor が返す (1クリップ分)
ProcessingResult          ← パイプライン全体の最終結果
```

---

## VideoInfo

```python
@dataclass
class VideoInfo:
    path: str
    fps: float
    width: int
    height: int
    total_frames: int
    duration_sec: float
    codec: str
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| path | str | 入力動画の絶対パス |
| fps | float | フレームレート |
| width / height | int | 解像度 |
| total_frames | int | 総フレーム数 |
| duration_sec | float | 総再生時間（秒） |
| codec | str | 入力コーデック識別子 |

---

## CycleBoundary

```python
@dataclass
class CycleBoundary:
    cycle_id: int          # 1始まり
    start_frame: int       # サイクル開始フレーム番号
    end_frame: int         # 次サイクル開始フレーム番号 - 1
    start_sec: float       # サイクル開始時刻（秒）
    end_sec: float         # サイクル終了時刻（秒）
    similarity_score: float  # 基準フレームとの類似度
```

- `end_frame` は「次サイクルの start_frame - 1」とする
- 最後のサイクルの `end_frame` は動画の末尾フレーム

---

## Segment

```python
@dataclass
class Segment:
    cycle_id: int
    source_start_frame: int  # 元動画でのフレーム番号
    source_end_frame: int
    source_start_sec: float
    source_end_sec: float
    clip_path: str           # 一時ファイルパス (tmp/clip_001.mp4)
```

---

## ProcessingResult

```python
@dataclass
class ProcessingResult:
    input_path: str
    output_path: str
    detected_cycles: int
    extracted_segments: int
    skipped_cycles: List[int]   # 区間が範囲外のサイクルID
    cycle_boundaries: List[CycleBoundary]
    segments: List[Segment]
    processing_time_sec: float
    warnings: List[str]
```

---

## 設定スキーマ（Pydantic v2）

```python
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
from typing import Optional, Tuple, Literal

class InputConfig(BaseModel):
    video_path: Path
    reference_frame: Optional[int] = None   # 手動モード
    auto_detect: bool = False               # 自動モード
    
    @field_validator("video_path")
    def must_exist(cls, v):
        if not v.exists():
            raise ValueError(f"動画ファイルが見つかりません: {v}")
        return v

class CycleConfig(BaseModel):
    similarity_threshold: float = Field(0.92, ge=0.0, le=1.0)
    min_cycle_frames: int = Field(30, ge=1)   # 誤検出防止の最短サイクル長
    scan_stride: int = Field(5, ge=1)          # 高速化のためN枚おきにスキャン
    refine_window: int = Field(10, ge=0)       # ピーク周辺の精細スキャン幅(フレーム)
    similarity_method: Literal["histogram", "orb", "ssim", "combined"] = "histogram"

class ExtractionConfig(BaseModel):
    start_offset_sec: float = Field(0.0, ge=0.0)
    end_offset_sec: float
    
    @field_validator("end_offset_sec")
    def end_after_start(cls, v, info):
        if "start_offset_sec" in info.data and v <= info.data["start_offset_sec"]:
            raise ValueError("end_offset_sec は start_offset_sec より大きい値にしてください")
        return v

class OverlayConfig(BaseModel):
    enabled: bool = True
    text_template: str = "Cycle {n}"          # {n}=番号, {t}=タイムスタンプ
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "top-left"
    margin_px: int = 20
    font_scale: float = 1.5
    font_thickness: int = 2
    color: Tuple[int, int, int] = (255, 255, 255)   # BGR
    background_color: Optional[Tuple[int, int, int]] = (0, 0, 0)
    background_alpha: float = Field(0.5, ge=0.0, le=1.0)
    show_timestamp: bool = False

class OutputConfig(BaseModel):
    video_path: Path
    fps: Optional[float] = None               # None = 入力FPSを継承
    bitrate: str = "5M"
    codec: str = "libx264"
    audio: bool = False                       # 工場動画は音声不要のケースが多い
    temp_dir: Path = Path("./tmp")

class AppConfig(BaseModel):
    input: InputConfig
    cycle: CycleConfig
    extraction: ExtractionConfig
    overlay: OverlayConfig
    output: OutputConfig
```

---

## 設定ファイル例（config.yaml）

```yaml
input:
  video_path: "./factory_video.mp4"
  reference_frame: 150       # ロボットがホーム位置にある代表フレーム

cycle:
  similarity_threshold: 0.92
  min_cycle_frames: 30
  scan_stride: 5
  refine_window: 10
  similarity_method: "histogram"

extraction:
  start_offset_sec: 2.0
  end_offset_sec: 8.0

overlay:
  enabled: true
  text_template: "Cycle {n}"
  position: "top-left"
  font_scale: 1.5
  color: [255, 255, 255]
  background_color: [0, 0, 0]
  background_alpha: 0.5
  show_timestamp: false

output:
  video_path: "./output.mp4"
  fps: null
  bitrate: "5M"
  codec: "libx264"
  audio: false
  temp_dir: "./tmp"
```

---

## カスタム例外

```python
class VideoEditorError(Exception):
    """基底例外"""

class VideoLoadError(VideoEditorError):
    """動画ファイルの読み込み失敗"""

class ReferenceFrameError(VideoEditorError):
    """基準フレーム番号が範囲外など"""

class CycleDetectionError(VideoEditorError):
    """サイクルが1つも検出できなかった"""

class SegmentExtractionError(VideoEditorError):
    """切り出し区間が不正"""

class OverlayError(VideoEditorError):
    """ナンバリング合成失敗"""

class ConcatError(VideoEditorError):
    """動画結合失敗"""
```
