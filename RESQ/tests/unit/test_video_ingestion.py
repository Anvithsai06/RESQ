"""
Unit tests for video ingestion (WORKFLOW.md Phase 2).

Uses a small synthetic video generated on the fly rather than the real demo
footage, so these tests are hermetic and don't depend on
data/demo/emergency_scene.mp4 being present.
"""
import cv2
import numpy as np
import pytest

from vision.video.ingestion import Frame, VideoOpenError, VideoSource

FPS = 10.0
WIDTH, HEIGHT = 64, 48
TOTAL_FRAMES = 20


@pytest.fixture
def synthetic_video(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    writer = cv2.VideoWriter(
        str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT)
    )
    for i in range(TOTAL_FRAMES):
        frame = np.full((HEIGHT, WIDTH, 3), fill_value=i % 256, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return video_path


def test_missing_video_raises():
    with pytest.raises(VideoOpenError):
        VideoSource("data/does/not/exist.mp4", camera_id="CAM-01")


def test_reads_all_frames_at_sample_rate_1(synthetic_video):
    with VideoSource(synthetic_video, camera_id="CAM-01", sample_rate=1) as source:
        frames = list(source.frames())

    assert len(frames) == TOTAL_FRAMES
    assert all(isinstance(f, Frame) for f in frames)
    assert [f.frame_index for f in frames] == list(range(TOTAL_FRAMES))


def test_frame_dimensions_and_camera_id(synthetic_video):
    with VideoSource(synthetic_video, camera_id="CAM-01", sample_rate=1) as source:
        first = next(source.frames())

    assert first.camera_id == "CAM-01"
    assert first.frame_width == WIDTH
    assert first.frame_height == HEIGHT
    assert first.image.shape == (HEIGHT, WIDTH, 3)


def test_deterministic_timestamps(synthetic_video):
    with VideoSource(synthetic_video, camera_id="CAM-01", sample_rate=1) as source:
        frames = list(source.frames())

    for f in frames:
        assert f.timestamp == pytest.approx(f.frame_index / f.source_fps)


def test_frame_sampling_interval(synthetic_video):
    with VideoSource(synthetic_video, camera_id="CAM-01", sample_rate=5) as source:
        frames = list(source.frames())

    assert [f.frame_index for f in frames] == [0, 5, 10, 15]


def test_invalid_sample_rate_rejected(synthetic_video):
    with pytest.raises(ValueError):
        VideoSource(synthetic_video, camera_id="CAM-01", sample_rate=0)


def test_end_of_video_handled_cleanly(synthetic_video):
    with VideoSource(synthetic_video, camera_id="CAM-01", sample_rate=1) as source:
        frames = list(source.frames())
        # Iterating again after exhaustion should not raise or hang.
        frames_again = list(source.frames())

    assert len(frames) == TOTAL_FRAMES
    assert frames_again == []
