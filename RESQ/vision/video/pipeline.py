"""
Golden-rule vertical slice (CLAUDE.md):

    Video → YOLO → ByteTrack → annotated video

Get this working before touching zones, temporal state, priority, or
notifications. This is *not* the full Phase 14 integration (which adds
zones, temporal state, priority, notification, and the dashboard) — just
the minimal slice proving detection + tracking work end-to-end on real
footage.
"""
from __future__ import annotations

from pathlib import Path

from vision.detection.detector import Detector
from vision.tracking.byte_tracker import ByteTracker
from vision.video.annotate import AnnotatedVideoWriter, draw_tracks
from vision.video.ingestion import VideoSource


def run_vertical_slice(
    video_path: str | Path,
    camera_id: str,
    detector: Detector,
    tracker: ByteTracker,
    output_path: str | Path,
    sample_rate: int = 1,
) -> int:
    """Runs Video → Detector → Tracker → annotated video.

    Returns the number of annotated frames written.
    """
    with VideoSource(video_path, camera_id=camera_id, sample_rate=sample_rate) as source:
        writer = AnnotatedVideoWriter(
            output_path,
            fps=source.fps / sample_rate,
            frame_size=(source.frame_width, source.frame_height),
        )
        frames_written = 0
        try:
            for frame in source.frames():
                detections = detector.detect(frame)
                tracks = tracker.update(detections, frame.timestamp)
                writer.write(draw_tracks(frame.image, tracks))
                frames_written += 1
        finally:
            writer.release()
    return frames_written


if __name__ == "__main__":
    import argparse

    from backend.config.settings import settings
    from vision.detection.detector import create_default_detector

    parser = argparse.ArgumentParser(
        description="Run the RESQ vertical slice: video -> annotated video (no zones/priority/notifications)."
    )
    parser.add_argument("--video", default=settings.demo_video_path)
    parser.add_argument("--camera-id", default="CAM-01")
    parser.add_argument("--output", default="data/demo/annotated_output.mp4")
    args = parser.parse_args()

    detector = create_default_detector(
        model_path=settings.yolo_model_path,
        model_versions_path="configs/model_versions.json",
        confidence_threshold=settings.yolo_confidence_threshold,
    )
    tracker = ByteTracker(camera_id=args.camera_id)

    count = run_vertical_slice(
        args.video, args.camera_id, detector, tracker, args.output, sample_rate=settings.frame_sample_rate
    )
    print(f"Wrote {count} annotated frames to {args.output}")
