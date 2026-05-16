from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterator, Optional, Tuple

import cv2
import numpy as np

from .exceptions import VideoLoadError
from .models import VideoInfo


class VideoLoader:
    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._info: Optional[VideoInfo] = None

    def load(self, path: str | Path) -> VideoInfo:
        path = str(path)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise VideoLoadError(f"動画ファイルを開けません: {path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = self._probe_fps(path)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frames / fps if fps > 0 else 0.0
        codec = self._probe_codec(path)

        if self._cap is not None:
            self._cap.release()
        self._cap = cap
        self._info = VideoInfo(
            path=path,
            fps=fps,
            width=width,
            height=height,
            total_frames=total_frames,
            duration_sec=duration_sec,
            codec=codec,
        )
        return self._info

    def get_frame(self, frame_num: int) -> np.ndarray:
        if self._cap is None or self._info is None:
            raise RuntimeError("load() を先に呼び出してください")
        if not (0 <= frame_num < self._info.total_frames):
            raise IndexError(
                f"フレーム番号 {frame_num} は範囲外です "
                f"(0〜{self._info.total_frames - 1})"
            )
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self._cap.read()
        if not ret:
            raise VideoLoadError(f"フレーム {frame_num} を読み込めませんでした")
        return frame

    def iter_frames(
        self,
        start: int,
        end: int,
        stride: int = 1,
    ) -> Iterator[Tuple[int, np.ndarray]]:
        for i in range(start, end, stride):
            yield i, self.get_frame(i)

    def scan_sequential(self, stride: int = 1) -> Iterator[Tuple[int, np.ndarray]]:
        """全フレームを順次読み込み、stride おきにフレームを yield する。
        get_frame よりも高速（シーク不要）。"""
        if self._info is None:
            raise RuntimeError("load() を先に呼び出してください")
        cap = cv2.VideoCapture(self._info.path)
        frame_num = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_num % stride == 0:
                    yield frame_num, frame
                frame_num += 1
        finally:
            cap.release()

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _probe_fps(self, path: str) -> float:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=r_frame_rate",
                    "-of", "json", path,
                ],
                capture_output=True, text=True, check=True,
            )
            data = json.loads(result.stdout)
            num, den = data["streams"][0]["r_frame_rate"].split("/")
            return float(num) / float(den)
        except Exception:
            return 30.0

    def _probe_codec(self, path: str) -> str:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name",
                    "-of", "json", path,
                ],
                capture_output=True, text=True, check=True,
            )
            data = json.loads(result.stdout)
            return data["streams"][0]["codec_name"]
        except Exception:
            return "unknown"

    def __enter__(self) -> "VideoLoader":
        return self

    def __exit__(self, *args: object) -> None:
        self.release()
