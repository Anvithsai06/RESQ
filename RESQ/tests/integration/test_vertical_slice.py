"""
Integration test for the golden-rule vertical slice (CLAUDE.md):

    Video → YOLO → ByteTrack → annotated video

Uses a synthetic video and a fake detection backend (no YOLO weights are
committed to the repo — see models/README / .gitignore) so this proves the
ingestion → detection → tracking → annotated-output wiring is correct
without depending on real model weights or demo footage.
"""
import cv2
import numpy as np
import pytest

from vision.detection.detector import Detector, ModelClassConfig
from vision.tracking.byte_tracker import ByteTracker
from vision.video.pipeline import run_vertical_slice

FPS = 10.0
WIDTH, HEIGHT = 64, 48
TOTAL_FRAMES = 6


class FakeMovingPersonBackend:
    """Simulates YOLO always finding one confident 'person' box that drifts
    slightly frame to frame — enough for ByteTrack to keep a stable ID."""

    def __init__(self):
        self._frame_count = 0

    def infer(self, image, confidence_threshold):
        x = 5 + self._frame_count
        self._frame_count += 1
        return [("person", 0.9, (float(x), 5.0, float(x + 20), 35.0))]


@pytest.fixture
def synthetic_video(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    for i in range(TOTAL_FRAMES):
        frame = np.full((HEIGHT, WIDTH, 3), fill_value=i % 256, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return video_path


def test_vertical_slice_writes_annotated_video(tmp_path, synthetic_video):
    class_config = ModelClassConfig(validated_classes={"person"}, experimental_classes={"fire", "smoke"})
    detector = Detector(FakeMovingPersonBackend(), class_config, confidence_threshold=0.5)
    tracker = ByteTracker(camera_id="CAM-01")
    output_path = tmp_path / "annotated.mp4"

    frames_written = run_vertical_slice(
        synthetic_video, camera_id="CAM-01", detector=detector, tracker=tracker, output_path=output_path
    )

    assert frames_written == TOTAL_FRAMES
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    readback = cv2.VideoCapture(str(output_path))
    assert readback.isOpened()
    assert int(readback.get(cv2.CAP_PROP_FRAME_COUNT)) == TOTAL_FRAMES
    readback.release()


def test_vertical_slice_produces_stable_track_id_across_frames(tmp_path, synthetic_video):
    class_config = ModelClassConfig(validated_classes={"person"}, experimental_classes=set())
    detector = Detector(FakeMovingPersonBackend(), class_config, confidence_threshold=0.5)
    tracker = ByteTracker(camera_id="CAM-01")

    seen_track_ids = []

    # Re-run the same per-frame steps `run_vertical_slice` performs, but
    # capture track IDs directly instead of just the rendered video.
    from vision.video.ingestion import VideoSource

    with VideoSource(synthetic_video, camera_id="CAM-01") as source:
        for frame in source.frames():
            detections = detector.detect(frame)
            tracks = tracker.update(detections, frame.timestamp)
            assert len(tracks) == 1
            seen_track_ids.append(tracks[0].track_id)

    assert len(set(seen_track_ids)) == 1
