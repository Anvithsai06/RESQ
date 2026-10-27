"""
Annotated video output — supports the golden-rule vertical slice
(CLAUDE.md): Video → YOLO → ByteTrack → annotated video.

Pure drawing/writing helpers; no detection or tracking logic lives here.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

_BOX_COLOR = (0, 200, 0)
_TEXT_COLOR = (255, 255, 255)


def draw_tracks(image: np.ndarray, tracks: list) -> np.ndarray:
    """Draws each track's bbox + "CLASS_NAME 0.94 #track_id" label onto a
    copy of `image`. `tracks` is a list of
    vision.tracking.byte_tracker.Track."""
    annotated = image.copy()
    for track in tracks:
        x1, y1, x2, y2 = (int(round(v)) for v in track.bbox)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), _BOX_COLOR, 2)
        label = f"{track.class_name.upper()} {track.confidence:.2f} #{track.track_id}"
        cv2.putText(
            annotated,
            label,
            (x1, max(y1 - 8, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            _TEXT_COLOR,
            1,
            cv2.LINE_AA,
        )
    return annotated


# Browsers (Chrome/Safari) cannot decode OpenCV's default "mp4v" output —
# that's MPEG-4 Part 2, which no major browser ships a decoder for. The
# dashboard plays this file in a <video> element, so H.264 ("avc1") is
# required; "mp4v" is kept only as a last-resort fallback for environments
# whose OpenCV build lacks an H.264 encoder (the file still writes, it just
# won't play in-browser).
_PREFERRED_FOURCCS = ("avc1", "H264", "mp4v")


class AnnotatedVideoWriter:
    """Wraps cv2.VideoWriter for writing the annotated output video."""

    def __init__(self, output_path: str | Path, fps: float, frame_size: tuple[int, int]):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        self._writer = None
        self.codec: str | None = None
        for fourcc_name in _PREFERRED_FOURCCS:
            writer = cv2.VideoWriter(
                str(self.output_path), cv2.VideoWriter_fourcc(*fourcc_name), fps, frame_size
            )
            if writer.isOpened():
                self._writer = writer
                self.codec = fourcc_name
                break
            writer.release()

        if self._writer is None:
            raise RuntimeError(f"Could not open video writer for: {self.output_path}")

    def write(self, image: np.ndarray) -> None:
        self._writer.write(image)

    def release(self) -> None:
        if self._writer is not None and self._writer.isOpened():
            self._writer.release()

    def __enter__(self) -> "AnnotatedVideoWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
