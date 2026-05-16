from __future__ import annotations

import logging
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Callable, List

from .config import OverlayConfig
from .exceptions import OverlayError
from .models import Segment

logger = logging.getLogger(__name__)

_POSITION_MAP = {
    "top-left":     "x={m}:y={m}",
    "top-right":    "x=w-text_w-{m}:y={m}",
    "bottom-left":  "x={m}:y=h-text_h-{m}",
    "bottom-right": "x=w-text_w-{m}:y=h-text_h-{m}",
}


def _escape(text: str) -> str:
    """FFmpeg drawtext 用にテキストをエスケープする。"""
    return (
        text.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
    )


class NumberingOverlay:
    def __init__(self, config: OverlayConfig) -> None:
        self._config = config

    def _format_text(self, cycle_id: int, start_sec: float) -> str:
        t = str(timedelta(seconds=int(start_sec)))
        return self._config.text_template.format(n=cycle_id, t=t)

    def _build_drawtext_filter(self, text: str) -> str:
        cfg = self._config
        r, g, b = cfg.color
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        font_size = max(12, int(cfg.font_scale * 24))
        pos = _POSITION_MAP[cfg.position].format(m=cfg.margin_px)

        parts = [
            f"drawtext=text='{_escape(text)}'",
            f"fontsize={font_size}",
            f"fontcolor={color_hex}",
            pos,
        ]

        if cfg.background_color is not None:
            br, bg, bb = cfg.background_color
            bg_hex = f"#{br:02x}{bg:02x}{bb:02x}"
            parts += [
                "box=1",
                f"boxcolor={bg_hex}@{cfg.background_alpha}",
                "boxborderw=5",
            ]

        return ":".join(parts)

    def apply_to_clip(self, segment: Segment) -> Segment:
        if not self._config.enabled:
            return segment

        text = self._format_text(segment.cycle_id, segment.source_start_sec)
        vf = self._build_drawtext_filter(text)

        input_path = segment.clip_path
        output_path = str(Path(input_path).with_suffix("")) + "_ov.mp4"

        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-an",
            "-y", output_path,
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise OverlayError(
                f"Cycle {segment.cycle_id} のオーバーレイ適用に失敗しました: "
                f"{e.stderr.decode(errors='replace')}"
            )

        logger.debug(f"Cycle {segment.cycle_id}: オーバーレイ適用 → {output_path}")
        return Segment(
            cycle_id=segment.cycle_id,
            source_start_frame=segment.source_start_frame,
            source_end_frame=segment.source_end_frame,
            source_start_sec=segment.source_start_sec,
            source_end_sec=segment.source_end_sec,
            clip_path=output_path,
        )

    def apply_all(
        self,
        segments: List[Segment],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[Segment]:
        results: List[Segment] = []
        total = len(segments)
        for i, segment in enumerate(segments):
            results.append(self.apply_to_clip(segment))
            if progress_callback:
                progress_callback((i + 1) / total)
        return results
