from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from .config import ExtractionConfig, OutputConfig
from .exceptions import SegmentExtractionError
from .models import CycleBoundary, Segment, VideoInfo

logger = logging.getLogger(__name__)


class SegmentExtractor:
    def __init__(self, config: ExtractionConfig, output_config: OutputConfig) -> None:
        self._config = config
        self._output_config = output_config

    def validate(self, boundary: CycleBoundary, video: VideoInfo) -> bool:
        """オフセット指定がサイクル長に収まるか確認する。"""
        cycle_duration = boundary.end_sec - boundary.start_sec
        if self._config.end_offset_sec > cycle_duration:
            logger.warning(
                f"Cycle {boundary.cycle_id}: 切り出し終了オフセット "
                f"({self._config.end_offset_sec}秒) が "
                f"サイクル長 ({cycle_duration:.2f}秒) を超えています。スキップします。"
            )
            return False
        return True

    def extract(self, boundary: CycleBoundary, video: VideoInfo) -> Segment:
        """1サイクル分の区間をFFmpegで切り出す。"""
        cut_start = boundary.start_sec + self._config.start_offset_sec
        cut_end = boundary.start_sec + self._config.end_offset_sec

        temp_dir = Path(self._output_config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        clip_path = str(temp_dir / f"clip_{boundary.cycle_id:03d}.mp4")

        # -ss を -i の後に置くことで精度優先の切り出しを行う
        cmd = [
            "ffmpeg",
            "-i", video.path,
            "-ss", str(cut_start),
            "-to", str(cut_end),
            "-c:v", self._output_config.codec,
            "-b:v", self._output_config.bitrate,
        ]
        if not self._output_config.audio:
            cmd.append("-an")
        cmd += ["-y", clip_path]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise SegmentExtractionError(
                f"Cycle {boundary.cycle_id} の切り出しに失敗しました: "
                f"{e.stderr.decode(errors='replace')}"
            )

        logger.debug(
            f"Cycle {boundary.cycle_id}: "
            f"{cut_start:.2f}秒 〜 {cut_end:.2f}秒 → {clip_path}"
        )
        return Segment(
            cycle_id=boundary.cycle_id,
            source_start_frame=int(cut_start * video.fps),
            source_end_frame=int(cut_end * video.fps),
            source_start_sec=cut_start,
            source_end_sec=cut_end,
            clip_path=clip_path,
        )

    def extract_all(
        self,
        boundaries: List[CycleBoundary],
        video: VideoInfo,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[Segment]:
        segments: List[Segment] = []
        total = len(boundaries)
        for i, boundary in enumerate(boundaries):
            if self.validate(boundary, video):
                segments.append(self.extract(boundary, video))
            if progress_callback:
                progress_callback((i + 1) / total)
        return segments
