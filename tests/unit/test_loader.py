from __future__ import annotations

import numpy as np
import pytest

from video_editor.exceptions import VideoLoadError
from video_editor.loader import VideoLoader


class TestVideoLoader:
    def test_load_valid_video(self, test_video_avi_path):
        loader = VideoLoader()
        info = loader.load(str(test_video_avi_path))
        assert info.fps == pytest.approx(30.0, abs=1.0)
        assert info.total_frames == 5 * 3 * 30  # 5サイクル × 3秒 × 30fps
        assert info.width == 320
        assert info.height == 240
        loader.release()

    def test_load_nonexistent_file(self):
        with pytest.raises(VideoLoadError):
            VideoLoader().load("nonexistent_file_xyz.mp4")

    def test_get_frame_shape(self, loader_with_avi):
        frame = loader_with_avi.get_frame(0)
        assert frame.shape == (240, 320, 3)
        assert frame.dtype == np.uint8

    def test_get_frame_out_of_range(self, loader_with_avi):
        info = loader_with_avi._info
        with pytest.raises(IndexError):
            loader_with_avi.get_frame(info.total_frames + 1)

    def test_get_frame_negative_index(self, loader_with_avi):
        with pytest.raises(IndexError):
            loader_with_avi.get_frame(-1)

    def test_iter_frames_count(self, loader_with_avi):
        frames = list(loader_with_avi.iter_frames(0, 10, stride=2))
        assert len(frames) == 5  # 0, 2, 4, 6, 8
        frame_nums = [fn for fn, _ in frames]
        assert frame_nums == [0, 2, 4, 6, 8]

    def test_scan_sequential_count(self, loader_with_avi):
        frames = list(loader_with_avi.scan_sequential(stride=30))
        expected = loader_with_avi._info.total_frames // 30
        assert len(frames) >= expected

    def test_context_manager(self, test_video_avi_path):
        with VideoLoader() as loader:
            info = loader.load(str(test_video_avi_path))
            assert info.total_frames > 0
        # 解放後は _cap が None になっていること
        assert loader._cap is None

    def test_load_duration(self, test_video_avi_path):
        loader = VideoLoader()
        info = loader.load(str(test_video_avi_path))
        # 5サイクル × 3秒 = 15秒
        assert info.duration_sec == pytest.approx(15.0, abs=0.5)
        loader.release()
