from __future__ import annotations

import logging
from typing import Callable, List, Optional

import cv2
import numpy as np
from scipy import signal

from .config import CycleConfig
from .exceptions import CycleDetectionError, ReferenceFrameError
from .loader import VideoLoader
from .models import CycleBoundary, VideoInfo

logger = logging.getLogger(__name__)


class CycleDetector:
    def __init__(self, config: CycleConfig) -> None:
        self._config = config
        self._ref_hist: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ #
    # 基準フレーム設定
    # ------------------------------------------------------------------ #

    def set_reference_frame(self, frame: np.ndarray) -> None:
        self._ref_hist = self._compute_histogram(frame)

    def _compute_histogram(self, frame: np.ndarray) -> np.ndarray:
        small = cv2.resize(frame, (256, 256))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        h_hist = cv2.calcHist([hsv], [0], None, [50], [0, 180])
        s_hist = cv2.calcHist([hsv], [1], None, [60], [0, 256])
        hist = np.concatenate([h_hist.flatten(), s_hist.flatten()])
        cv2.normalize(hist, hist)
        return hist

    # ------------------------------------------------------------------ #
    # 類似度計算
    # ------------------------------------------------------------------ #

    def compute_similarity(self, frame: np.ndarray) -> float:
        if self._ref_hist is None:
            raise ReferenceFrameError(
                "set_reference_frame() を先に呼び出してください"
            )
        hist = self._compute_histogram(frame)
        return float(cv2.compareHist(self._ref_hist, hist, cv2.HISTCMP_CORREL))

    # ------------------------------------------------------------------ #
    # スキャン（全フレームの類似度計算）
    # ------------------------------------------------------------------ #

    def scan(
        self,
        loader: VideoLoader,
        video: VideoInfo,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[float]:
        """動画全体を順次スキャンして各フレームの類似度リストを返す。
        scan_stride おきに計算し、中間フレームは前の値で埋める。"""
        if self._ref_hist is None:
            raise ReferenceFrameError(
                "set_reference_frame() を先に呼び出してください"
            )

        similarities = [0.0] * video.total_frames
        stride = self._config.scan_stride
        last_sim = 0.0
        total = video.total_frames

        for frame_num, frame in loader.scan_sequential(stride):
            last_sim = self.compute_similarity(frame)
            # stride 間のフレームを前の値で埋める
            for j in range(frame_num, min(frame_num + stride, total)):
                similarities[j] = last_sim
            if progress_callback and frame_num % (stride * 10) == 0:
                progress_callback(frame_num / total)

        if progress_callback:
            progress_callback(1.0)

        return similarities

    # ------------------------------------------------------------------ #
    # ピーク検出
    # ------------------------------------------------------------------ #

    def detect_peaks(self, similarities: List[float]) -> List[int]:
        arr = np.array(similarities)
        peaks, _ = signal.find_peaks(
            arr,
            height=self._config.similarity_threshold,
            distance=self._config.min_cycle_frames,
        )
        peaks_list = peaks.tolist()

        # scipy は境界(index 0)をピークとして検出しない。
        # 先頭フレームが閾値以上かつ最初の検出ピークと十分離れている場合は追加する。
        if (
            len(arr) > 0
            and arr[0] >= self._config.similarity_threshold
            and (not peaks_list or peaks_list[0] >= self._config.min_cycle_frames)
        ):
            peaks_list = [0] + peaks_list

        return peaks_list

    def _refine_peak(
        self,
        loader: VideoLoader,
        approximate_peak: int,
        video: VideoInfo,
    ) -> int:
        """ピーク周辺を精細スキャンして実際の最大類似度フレームを返す。"""
        w = self._config.refine_window
        start = max(0, approximate_peak - w)
        end = min(video.total_frames, approximate_peak + w + 1)

        best_sim = -1.0
        best_frame = approximate_peak
        for frame_num in range(start, end):
            frame = loader.get_frame(frame_num)
            sim = self.compute_similarity(frame)
            if sim > best_sim:
                best_sim = sim
                best_frame = frame_num
        return best_frame

    # ------------------------------------------------------------------ #
    # サイクル検出（メイン処理）
    # ------------------------------------------------------------------ #

    def detect_cycles(
        self,
        loader: VideoLoader,
        video: VideoInfo,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[CycleBoundary]:
        similarities = self.scan(loader, video, progress_callback)
        peaks = self.detect_peaks(similarities)

        if not peaks:
            raise CycleDetectionError(
                f"サイクルが検出できませんでした。"
                f"--threshold を下げてみてください "
                f"(現在: {self._config.similarity_threshold})"
            )

        logger.debug(f"粗いピーク検出: {len(peaks)} 件")
        refined = sorted({self._refine_peak(loader, p, video) for p in peaks})
        logger.info(f"サイクル検出完了: {len(refined)} 件")

        boundaries: List[CycleBoundary] = []
        for i, start_frame in enumerate(refined):
            end_frame = (
                refined[i + 1] - 1 if i + 1 < len(refined) else video.total_frames - 1
            )
            boundaries.append(
                CycleBoundary(
                    cycle_id=i + 1,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    start_sec=start_frame / video.fps,
                    end_sec=end_frame / video.fps,
                    similarity_score=similarities[start_frame],
                )
            )

        return boundaries

    # ------------------------------------------------------------------ #
    # デバッグ用可視化
    # ------------------------------------------------------------------ #

    def visualize(
        self,
        similarities: List[float],
        boundaries: List[CycleBoundary],
        output_path: str,
    ) -> None:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib が見つかりません。可視化をスキップします。")
            return

        fig, ax = plt.subplots(figsize=(16, 4))
        ax.plot(similarities, linewidth=0.8, color="steelblue", label="similarity")
        ax.axhline(
            self._config.similarity_threshold,
            color="red", linestyle="--", linewidth=1,
            label=f"threshold={self._config.similarity_threshold}",
        )
        for b in boundaries:
            ax.axvline(b.start_frame, color="green", linewidth=1, alpha=0.7)
        ax.set_xlabel("フレーム番号")
        ax.set_ylabel("類似度")
        ax.set_title("サイクル検出結果")
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_path, dpi=100)
        plt.close(fig)
        logger.info(f"類似度グラフを保存: {output_path}")
