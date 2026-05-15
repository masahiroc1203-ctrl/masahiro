from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Callable, List, Optional

from .config import AppConfig
from .concat import VideoConcat
from .cycle_detector import CycleDetector
from .exceptions import ReferenceFrameError
from .extractor import SegmentExtractor
from .loader import VideoLoader
from .models import CycleBoundary, ProcessingResult
from .overlay import NumberingOverlay

logger = logging.getLogger(__name__)


class VideoEditingPipeline:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def run(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> ProcessingResult:
        start_time = time.time()
        temp_dir = Path(self._config.output.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        def report(stage: str, pct: float) -> None:
            logger.debug(f"{stage}: {int(pct * 100)}%")
            if progress_callback:
                progress_callback(stage, pct)

        try:
            # Step 1: 動画読み込み
            report("動画読み込み中", 0.0)
            loader = VideoLoader()
            video = loader.load(str(self._config.input.video_path))
            logger.info(
                f"動画情報: {video.width}x{video.height} @ {video.fps}fps, "
                f"{video.duration_sec:.1f}秒 ({video.total_frames}フレーム)"
            )
            report("動画読み込み完了", 1.0)

            # Step 2: 基準フレーム取得
            ref_num = self._config.input.reference_frame
            if ref_num is None:
                raise ReferenceFrameError(
                    "--ref-frame または config.yaml の reference_frame を指定してください"
                )
            ref_frame = loader.get_frame(ref_num)
            logger.info(
                f"基準フレーム: #{ref_num} ({ref_num / video.fps:.3f}秒)"
            )

            # Step 3: サイクル検出
            detector = CycleDetector(self._config.cycle)
            detector.set_reference_frame(ref_frame)
            boundaries = detector.detect_cycles(
                loader, video,
                progress_callback=lambda p: report("サイクル検出中", p),
            )
            logger.info(f"サイクル検出: {len(boundaries)} 件")

            # Step 4: 区間切り出し
            extractor = SegmentExtractor(self._config.extraction, self._config.output)
            segments = extractor.extract_all(
                boundaries, video,
                progress_callback=lambda p: report("区間切り出し中", p),
            )

            skipped = [
                b.cycle_id for b in boundaries
                if b.cycle_id not in {s.cycle_id for s in segments}
            ]
            if skipped:
                logger.warning(f"スキップされたサイクル: {skipped}")

            # Step 5: ナンバリングオーバーレイ
            overlay = NumberingOverlay(self._config.overlay)
            segments = overlay.apply_all(
                segments,
                progress_callback=lambda p: report("ナンバリング合成中", p),
            )

            # Step 6: 動画結合
            concat = VideoConcat(self._config.output)
            output_path = concat.concat(
                segments,
                self._config.output.video_path,
                progress_callback=lambda p: report("動画結合中", p),
            )

            loader.release()
            elapsed = time.time() - start_time

            return ProcessingResult(
                input_path=str(self._config.input.video_path),
                output_path=str(output_path),
                detected_cycles=len(boundaries),
                extracted_segments=len(segments),
                skipped_cycles=skipped,
                cycle_boundaries=boundaries,
                segments=segments,
                processing_time_sec=elapsed,
            )

        finally:
            shutil.rmtree(str(temp_dir), ignore_errors=True)

    def preview_detection(
        self,
        graph_output_path: str,
    ) -> List[CycleBoundary]:
        loader = VideoLoader()
        video = loader.load(str(self._config.input.video_path))
        ref_frame = loader.get_frame(self._config.input.reference_frame)

        detector = CycleDetector(self._config.cycle)
        detector.set_reference_frame(ref_frame)
        similarities = detector.scan(loader, video)
        boundaries = detector.detect_cycles(loader, video)

        detector.visualize(similarities, boundaries, graph_output_path)
        loader.release()
        return boundaries
