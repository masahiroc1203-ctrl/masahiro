"""サイクリックなテスト動画を生成するユーティリティ。

各サイクルの先頭フレームに白い四角を描画し、
それ以外のフレームはカラーグラデーションとする。
→ 白い四角フレームが基準フレームに相当。
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np


def create_cyclic_video(
    output_path: str | Path,
    cycle_count: int = 5,
    cycle_length_sec: float = 3.0,
    fps: int = 30,
    resolution: Tuple[int, int] = (320, 240),
) -> Path:
    """cv2.VideoWriter でサイクリックなテスト動画を生成する。"""
    output_path = Path(output_path)
    width, height = resolution

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    avi_path = output_path.with_suffix(".avi")
    writer = cv2.VideoWriter(str(avi_path), fourcc, fps, (width, height))

    frames_per_cycle = int(cycle_length_sec * fps)
    for _ in range(cycle_count):
        for f in range(frames_per_cycle):
            img = np.zeros((height, width, 3), dtype=np.uint8)
            if f == 0:
                # 基準フレーム: 中央に白い四角
                cv2.rectangle(
                    img,
                    (width // 4, height // 4),
                    (width * 3 // 4, height * 3 // 4),
                    (255, 255, 255),
                    -1,
                )
            else:
                t = f / frames_per_cycle
                img[:, :, 0] = int(255 * t)          # B: 徐々に増加
                img[:, :, 1] = int(128 * (1 - t))    # G: 徐々に減少
            writer.write(img)

    writer.release()

    # .mp4 が必要な場合は FFmpeg で変換
    if output_path.suffix.lower() == ".mp4":
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(avi_path),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output_path)],
            check=True, capture_output=True,
        )
        avi_path.unlink()
        return output_path

    return avi_path
