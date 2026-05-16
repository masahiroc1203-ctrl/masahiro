from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from .config import OutputConfig
from .exceptions import ConcatError
from .models import Segment

logger = logging.getLogger(__name__)


class VideoConcat:
    def __init__(self, config: OutputConfig) -> None:
        self._config = config

    def _write_concat_list(self, segments: List[Segment], list_path: Path) -> None:
        with open(list_path, "w", encoding="utf-8") as f:
            for segment in segments:
                # パスのシングルクォートをエスケープ
                escaped = segment.clip_path.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

    def concat(
        self,
        segments: List[Segment],
        output_path: str | Path,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        temp_dir = Path(self._config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        list_path = temp_dir / "concat_list.txt"

        self._write_concat_list(segments, list_path)

        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            "-y", str(output_path),
        ]

        if progress_callback:
            progress_callback(0.0)

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise ConcatError(
                f"動画結合に失敗しました: {e.stderr.decode(errors='replace')}"
            )

        if progress_callback:
            progress_callback(1.0)

        logger.info(f"結合完了: {output_path}")
        return output_path
