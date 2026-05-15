from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tests.fixtures.create_test_video import create_cyclic_video
from video_editor.config import CycleConfig, ExtractionConfig, OutputConfig, OverlayConfig
from video_editor.loader import VideoLoader
from video_editor.models import CycleBoundary, Segment, VideoInfo

# ------------------------------------------------------------------ #
# テスト動画フィクスチャ
# ------------------------------------------------------------------ #

@pytest.fixture(scope="session")
def test_video_path(tmp_path_factory) -> Path:
    """5サイクル × 3秒のテスト動画 (.mp4)"""
    p = tmp_path_factory.mktemp("video") / "cyclic.mp4"
    create_cyclic_video(p, cycle_count=5, cycle_length_sec=3.0, fps=30)
    return p


@pytest.fixture(scope="session")
def test_video_avi_path(tmp_path_factory) -> Path:
    """5サイクル × 3秒のテスト動画 (.avi) — FFmpegなし環境向け"""
    p = tmp_path_factory.mktemp("video") / "cyclic.avi"
    create_cyclic_video(p, cycle_count=5, cycle_length_sec=3.0, fps=30)
    return p


# ------------------------------------------------------------------ #
# VideoLoader フィクスチャ
# ------------------------------------------------------------------ #

@pytest.fixture()
def loader_with_avi(test_video_avi_path) -> VideoLoader:
    loader = VideoLoader()
    loader.load(str(test_video_avi_path))
    yield loader
    loader.release()


@pytest.fixture()
def video_info_avi(loader_with_avi, test_video_avi_path) -> VideoInfo:
    return loader_with_avi.load(str(test_video_avi_path))


# ------------------------------------------------------------------ #
# 参照フレーム・各種データフィクスチャ
# ------------------------------------------------------------------ #

@pytest.fixture()
def reference_frame() -> np.ndarray:
    """白い四角フレーム（基準フレームの代替）"""
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2_available = True
    try:
        import cv2
        cv2.rectangle(img, (80, 60), (240, 180), (255, 255, 255), -1)
    except ImportError:
        img[60:180, 80:240] = 255
    return img


@pytest.fixture()
def other_frame() -> np.ndarray:
    """基準と異なるフレーム（青いグラデーション）"""
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    img[:, :, 0] = 200  # B
    return img


@pytest.fixture()
def sample_boundary() -> CycleBoundary:
    return CycleBoundary(
        cycle_id=1,
        start_frame=0,
        end_frame=89,
        start_sec=0.0,
        end_sec=2.967,
        similarity_score=0.95,
    )


@pytest.fixture()
def cycle_config() -> CycleConfig:
    return CycleConfig(similarity_threshold=0.85, min_cycle_frames=30)


@pytest.fixture()
def extraction_config() -> ExtractionConfig:
    return ExtractionConfig(start_offset_sec=0.5, end_offset_sec=2.0)


@pytest.fixture()
def overlay_config() -> OverlayConfig:
    return OverlayConfig(enabled=True, text_template="Cycle {n}")


@pytest.fixture()
def output_config(tmp_path) -> OutputConfig:
    return OutputConfig(
        video_path=tmp_path / "output.mp4",
        temp_dir=tmp_path / "tmp",
    )
