from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Tuple

import yaml
from pydantic import BaseModel, Field, field_validator


class InputConfig(BaseModel):
    video_path: Path
    reference_frame: Optional[int] = None       # フレーム番号（後方互換）
    reference_time_sec: Optional[float] = None  # 動画の時刻（秒）← 優先
    auto_detect: bool = False

    @field_validator("video_path", mode="before")
    @classmethod
    def to_path(cls, v: object) -> Path:
        return Path(str(v))


class CycleConfig(BaseModel):
    similarity_threshold: float = Field(0.92, ge=0.0, le=1.0)
    min_cycle_frames: int = Field(30, ge=1)     # 内部処理用（フレーム数）
    min_cycle_sec: Optional[float] = None       # 最小サイクル時間（秒）← pipeline で変換
    scan_stride: int = Field(5, ge=1)
    refine_window: int = Field(10, ge=0)
    similarity_method: Literal["histogram", "combined"] = "histogram"
    roi: Optional[Tuple[float, float, float, float]] = None  # (x, y, w, h) 0-1の割合


class ExtractionConfig(BaseModel):
    before_sec: float = Field(0.0, ge=0.0)  # 検出フレームの何秒前から切り出すか
    after_sec: float = Field(5.0, ge=0.1)   # 検出フレームの何秒後まで切り出すか


class OverlayConfig(BaseModel):
    enabled: bool = True
    text_template: str = "Cycle {n}"
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right"] = "top-left"
    margin_px: int = 20
    font_scale: float = 1.5
    font_thickness: int = 2
    color: Tuple[int, int, int] = (255, 255, 255)
    background_color: Optional[Tuple[int, int, int]] = (0, 0, 0)
    background_alpha: float = Field(0.5, ge=0.0, le=1.0)
    show_timestamp: bool = False


class OutputConfig(BaseModel):
    video_path: Path
    fps: Optional[float] = None
    bitrate: str = "5M"
    codec: str = "libx264"
    audio: bool = False
    temp_dir: Path = Path("./tmp")

    @field_validator("video_path", "temp_dir", mode="before")
    @classmethod
    def to_path(cls, v: object) -> Path:
        return Path(str(v))


class AppConfig(BaseModel):
    input: InputConfig
    cycle: CycleConfig = Field(default_factory=CycleConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    overlay: OverlayConfig = Field(default_factory=OverlayConfig)
    output: OutputConfig


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if value is None:
            continue
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def load_config(
    config_path: Optional[Path],
    cli_overrides: Optional[dict] = None,
) -> AppConfig:
    base: dict = {}
    if config_path is not None and Path(config_path).exists():
        with open(config_path) as f:
            base = yaml.safe_load(f) or {}
    if cli_overrides:
        _deep_merge(base, cli_overrides)
    return AppConfig.model_validate(base)
