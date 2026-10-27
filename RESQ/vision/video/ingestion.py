"""
Video ingestion — WORKFLOW.md Phase 2.

Reads a prerecorded emergency video and yields sampled frames with
deterministic timestamps:

    Video → Decoder → Frame Sampling → Timestamp → Frame

This is the first stage of the pipeline only — no detection, tracking, or
intelligence logic lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np


class VideoOpenError(RuntimeError):
    """Raised when the configured video file cannot be opened or read."""


@dataclass
class Frame:
    image: np.ndarray
    frame_index: int  # 0-based index in the original (unsampled) video
    timestamp: float  # seconds — frame_index / source_fps, deterministic
    camera_id: str
    source_fps: float
    frame_width: int
    frame_height: int


class VideoSource:
    """
    Wraps a single prerecorded video file for one camera.

    Timestamps are derived from frame_index / source_fps rather than
    wall-clock time, so re-running the same video always produces the same
    timestamps regardless of processing speed.
    """

    def __init__(self, video_path: str | Path, camera_id: str, sample_rate: int = 1):
        """
        sample_rate: process every Nth frame (1 = every frame, 5 = every
        5th frame). Must be >= 1.
        """
        if sample_rate < 1:
            raise ValueError("sample_rate must be >= 1")

        self.video_path = Path(video_path)
        self.camera_id = camera_id
        self.sample_rate = sample_rate

        if not self.video_path.exists():
            raise VideoOpenError(f"Video file not found: {self.video_path}")

        self._cap = cv2.VideoCapture(str(self.video_path))
        if not self._cap.isOpened():
            raise VideoOpenError(f"OpenCV could not open video: {self.video_path}")

        fps = self._cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            self._cap.release()
            raise VideoOpenError(f"Could not determine FPS for video: {self.video_path}")
        self.fps: float = fps

        self.frame_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def frames(self) -> Iterator[Frame]:
        """Yield sampled frames in order; stops cleanly at end-of-video."""
        frame_index = 0
        try:
            while True:
                ok, image = self._cap.read()
                if not ok:
                    break  # end-of-video (or unreadable frame — treated the same)

                if frame_index % self.sample_rate == 0:
                    yield Frame(
                        image=image,
                        frame_index=frame_index,
                        timestamp=frame_index / self.fps,
                        camera_id=self.camera_id,
                        source_fps=self.fps,
                        frame_width=self.frame_width,
                        frame_height=self.frame_height,
                    )
                frame_index += 1
        finally:
            self.release()

    def release(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            self._cap.release()

    def __enter__(self) -> "VideoSource":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
