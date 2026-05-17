from __future__ import annotations

import numpy as np
import pytest

from video_editor.config import CycleConfig
from video_editor.cycle_detector import CycleDetector
from video_editor.exceptions import CycleDetectionError, ReferenceFrameError


class TestComputeSimilarity:
    def test_same_frame_returns_high_similarity(self, reference_frame):
        detector = CycleDetector(CycleConfig())
        detector.set_reference_frame(reference_frame)
        sim = detector.compute_similarity(reference_frame)
        assert sim > 0.99

    def test_different_frame_returns_low_similarity(self, reference_frame, other_frame):
        detector = CycleDetector(CycleConfig())
        detector.set_reference_frame(reference_frame)
        sim = detector.compute_similarity(other_frame)
        assert sim < 0.7

    def test_raises_without_reference(self, reference_frame):
        detector = CycleDetector(CycleConfig())
        with pytest.raises(ReferenceFrameError):
            detector.compute_similarity(reference_frame)

    def test_similarity_range(self, reference_frame, other_frame):
        detector = CycleDetector(CycleConfig())
        detector.set_reference_frame(reference_frame)
        for frame in [reference_frame, other_frame]:
            sim = detector.compute_similarity(frame)
            assert -1.0 <= sim <= 1.0


class TestDetectPeaks:
    def test_detects_peaks_above_threshold(self):
        config = CycleConfig(similarity_threshold=0.8, min_cycle_frames=10)
        detector = CycleDetector(config)
        # ピーク位置: 5, 25, 45, 65 (境界を避ける)
        sims = [0.1] * 80
        for i in [5, 25, 45, 65]:
            sims[i] = 0.95
        peaks = detector.detect_peaks(sims)
        assert len(peaks) == 4

    def test_min_distance_filter(self):
        config = CycleConfig(similarity_threshold=0.8, min_cycle_frames=15)
        detector = CycleDetector(config)
        # 近すぎるピーク: 0 と 5 は距離が 15 未満なのでどちらかが除去される
        sims = [0.1] * 50
        sims[0] = 0.95
        sims[5] = 0.90
        sims[30] = 0.95
        peaks = detector.detect_peaks(sims)
        assert len(peaks) == 2  # 0と30 (5は近すぎてフィルタされる)

    def test_no_peaks_below_threshold(self):
        config = CycleConfig(similarity_threshold=0.95)
        detector = CycleDetector(config)
        sims = [0.80] * 50
        peaks = detector.detect_peaks(sims)
        assert len(peaks) == 0


class TestDetectCycles:
    def test_correct_cycle_count(self, test_video_avi_path):
        """5サイクル動画から5件検出できること"""
        from video_editor.loader import VideoLoader

        loader = VideoLoader()
        video = loader.load(str(test_video_avi_path))
        reference = loader.get_frame(0)

        config = CycleConfig(similarity_threshold=0.85, min_cycle_frames=50)
        detector = CycleDetector(config)
        detector.set_reference_frame(reference)
        boundaries = detector.detect_cycles(loader, video)

        assert len(boundaries) == 5
        loader.release()

    def test_cycle_ids_are_sequential(self, test_video_avi_path):
        from video_editor.loader import VideoLoader

        loader = VideoLoader()
        video = loader.load(str(test_video_avi_path))
        reference = loader.get_frame(0)

        detector = CycleDetector(CycleConfig(similarity_threshold=0.85, min_cycle_frames=50))
        detector.set_reference_frame(reference)
        boundaries = detector.detect_cycles(loader, video)

        ids = [b.cycle_id for b in boundaries]
        assert ids == list(range(1, len(ids) + 1))
        loader.release()

    def test_raises_when_no_cycle_detected(self, test_video_avi_path):
        """動画に存在しないフレームを基準にした場合に例外を送出する"""
        from video_editor.loader import VideoLoader

        rng = np.random.default_rng(42)
        noise_frame = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8)

        loader = VideoLoader()
        video = loader.load(str(test_video_avi_path))

        detector = CycleDetector(CycleConfig(similarity_threshold=0.95))
        detector.set_reference_frame(noise_frame)

        with pytest.raises(CycleDetectionError):
            detector.detect_cycles(loader, video)
        loader.release()
