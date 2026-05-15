from dataclasses import dataclass, field
from typing import List


@dataclass
class VideoInfo:
    path: str
    fps: float
    width: int
    height: int
    total_frames: int
    duration_sec: float
    codec: str = ""


@dataclass
class CycleBoundary:
    cycle_id: int
    start_frame: int
    end_frame: int
    start_sec: float
    end_sec: float
    similarity_score: float


@dataclass
class Segment:
    cycle_id: int
    source_start_frame: int
    source_end_frame: int
    source_start_sec: float
    source_end_sec: float
    clip_path: str


@dataclass
class ProcessingResult:
    input_path: str
    output_path: str
    detected_cycles: int
    extracted_segments: int
    skipped_cycles: List[int] = field(default_factory=list)
    cycle_boundaries: List[CycleBoundary] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    processing_time_sec: float = 0.0
    warnings: List[str] = field(default_factory=list)
