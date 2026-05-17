from __future__ import annotations

import copy
import csv
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Callable, List, Optional

from .config import AppConfig
from .concat import VideoConcat
from .cycle_detector import CycleDetector
from .exceptions import CycleDetectionError, ReferenceFrameError
from .extractor import SegmentExtractor
from .loader import VideoLoader
from .models import CycleBoundary, ProcessingResult, Segment
from .overlay import NumberingOverlay

logger = logging.getLogger(__name__)


def _natural_sort_key(s: str) -> list:
    """ファイル名を数値部分込みで自然順ソートするキー。"""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


class VideoEditingPipeline:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------ #
    # 単一動画処理（内部共通処理）
    # ------------------------------------------------------------------ #

    def _load_reference_frame(self, video_path: Path) -> np.ndarray:
        """指定動画から基準フレームを1枚取り出して返す。"""
        import numpy as np
        loader = VideoLoader()
        video = loader.load(str(video_path))
        ref_time = self._config.input.reference_time_sec
        if ref_time is not None:
            ref_frame_num = min(int(ref_time * video.fps), video.total_frames - 1)
        elif self._config.input.reference_frame is not None:
            ref_frame_num = self._config.input.reference_frame
        else:
            raise ReferenceFrameError(
                "reference_time_sec または reference_frame を指定してください"
            )
        frame = loader.get_frame(ref_frame_num)
        loader.release()
        return frame

    def _process_single(
        self,
        video_path: Path,
        global_cycle_offset: int,
        progress_callback: Optional[Callable[[str, float], None]],
        shared_ref_frame=None,
    ) -> tuple[List[CycleBoundary], List[Segment]]:
        """1本の動画を処理してサイクル境界とセグメントを返す。"""

        def report(stage: str, pct: float) -> None:
            if progress_callback:
                progress_callback(stage, pct)

        loader = VideoLoader()
        video = loader.load(str(video_path))
        logger.info(
            f"{video_path.name}: {video.width}x{video.height} "
            f"@ {video.fps:.1f}fps, {video.duration_sec:.1f}秒"
        )

        # 基準フレーム：共有フレームが渡された場合はそれを使う
        if shared_ref_frame is not None:
            ref_frame = shared_ref_frame
        else:
            ref_time = self._config.input.reference_time_sec
            if ref_time is not None:
                ref_frame_num = min(int(ref_time * video.fps), video.total_frames - 1)
            elif self._config.input.reference_frame is not None:
                ref_frame_num = self._config.input.reference_frame
            else:
                raise ReferenceFrameError(
                    "reference_time_sec または reference_frame を指定してください"
                )
            ref_frame = loader.get_frame(ref_frame_num)

        # min_cycle_sec → min_cycle_frames に変換（動画ごとにFPSが異なる場合に対応）
        cycle_cfg = copy.copy(self._config.cycle)
        if cycle_cfg.min_cycle_sec is not None:
            cycle_cfg.min_cycle_frames = max(1, int(cycle_cfg.min_cycle_sec * video.fps))

        # サイクル検出
        detector = CycleDetector(cycle_cfg)
        detector.set_reference_frame(ref_frame)
        boundaries = detector.detect_cycles(
            loader, video,
            progress_callback=lambda p: report("サイクル検出中", p),
        )

        # グローバル通し番号に付け替え
        renumbered = [
            CycleBoundary(
                cycle_id=global_cycle_offset + i + 1,
                start_frame=b.start_frame,
                end_frame=b.end_frame,
                start_sec=b.start_sec,
                end_sec=b.end_sec,
                similarity_score=b.similarity_score,
                source_file=video_path.name,
            )
            for i, b in enumerate(boundaries)
        ]

        # 区間切り出し
        extractor = SegmentExtractor(self._config.extraction, self._config.output)
        segments = extractor.extract_all(
            renumbered, video,
            progress_callback=lambda p: report("区間切り出し中", p),
        )

        loader.release()
        return renumbered, segments

    # ------------------------------------------------------------------ #
    # 複数動画処理（メインエントリ）
    # ------------------------------------------------------------------ #

    def run_multi(
        self,
        video_paths: List[Path],
        output_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> ProcessingResult:
        """ファイル名順に複数動画を処理して1本に結合する。"""
        start_time = time.time()
        temp_dir = Path(self._config.output.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        sorted_paths = sorted(video_paths, key=lambda p: _natural_sort_key(p.name))
        logger.info(f"処理対象: {[p.name for p in sorted_paths]}")

        # 1本目の動画から基準フレームを1枚だけ取り出して全動画で共有する
        shared_ref_frame = self._load_reference_frame(sorted_paths[0])
        logger.info(f"基準フレームを {sorted_paths[0].name} から取得（全動画共通）")

        n = len(sorted_paths)
        all_boundaries: List[CycleBoundary] = []
        all_segments: List[Segment] = []
        global_offset = 0

        def make_cb(vi: int):
            def cb(stage: str, pct: float) -> None:
                overall = (vi + pct) / n
                if progress_callback:
                    progress_callback(f"[{vi+1}/{n}] {stage}", overall)
            return cb

        try:
            for vi, vpath in enumerate(sorted_paths):
                try:
                    boundaries, segments = self._process_single(
                        vpath, global_offset, make_cb(vi), shared_ref_frame
                    )
                except CycleDetectionError as e:
                    logger.warning(f"{vpath.name}: {e} → スキップ")
                    continue

                all_boundaries.extend(boundaries)
                all_segments.extend(segments)
                global_offset += len(boundaries)

            if not all_segments:
                raise CycleDetectionError("全ての動画でサイクルが検出できませんでした")

            # ナンバリングオーバーレイ
            if progress_callback:
                progress_callback("ナンバリング合成中", 0.0)
            overlay = NumberingOverlay(self._config.overlay)
            all_segments = overlay.apply_all(all_segments)

            # 結合
            if progress_callback:
                progress_callback("動画結合中", 0.0)
            concat = VideoConcat(self._config.output)
            final_path = concat.concat(all_segments, output_path)
            if progress_callback:
                progress_callback("完了", 1.0)

            skipped = [
                b.cycle_id for b in all_boundaries
                if b.cycle_id not in {s.cycle_id for s in all_segments}
            ]

            csv_path = output_path.with_suffix(".csv")
            self._write_csv(all_boundaries, csv_path)

            return ProcessingResult(
                input_path=str(sorted_paths),
                output_path=str(final_path),
                detected_cycles=len(all_boundaries),
                extracted_segments=len(all_segments),
                skipped_cycles=skipped,
                cycle_boundaries=all_boundaries,
                segments=all_segments,
                processing_time_sec=time.time() - start_time,
                csv_path=str(csv_path),
            )
        finally:
            shutil.rmtree(str(temp_dir), ignore_errors=True)

    @staticmethod
    def _write_csv(boundaries: List[CycleBoundary], csv_path: Path) -> None:
        def fmt_time(sec: float) -> str:
            m, s = divmod(int(sec), 60)
            return f"{m}:{s:02d}"

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["サイクル数", "ファイル名_時間"])
            for b in boundaries:
                writer.writerow([b.cycle_id, f"{b.source_file}_{fmt_time(b.start_sec)}"])

    # ------------------------------------------------------------------ #
    # 単一動画ショートカット（後方互換）
    # ------------------------------------------------------------------ #

    def run(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> ProcessingResult:
        return self.run_multi(
            [self._config.input.video_path],
            self._config.output.video_path,
            progress_callback,
        )

    def preview_detection(self, graph_output_path: str) -> List[CycleBoundary]:
        loader = VideoLoader()
        video = loader.load(str(self._config.input.video_path))

        ref_time = self._config.input.reference_time_sec
        ref_num = (
            min(int(ref_time * video.fps), video.total_frames - 1)
            if ref_time is not None
            else (self._config.input.reference_frame or 0)
        )
        ref_frame = loader.get_frame(ref_num)

        cycle_cfg = copy.copy(self._config.cycle)
        if cycle_cfg.min_cycle_sec is not None:
            cycle_cfg.min_cycle_frames = max(1, int(cycle_cfg.min_cycle_sec * video.fps))

        detector = CycleDetector(cycle_cfg)
        detector.set_reference_frame(ref_frame)
        similarities = detector.scan(loader, video)
        boundaries = detector.detect_cycles(loader, video)
        detector.visualize(similarities, boundaries, graph_output_path)
        loader.release()
        return boundaries
