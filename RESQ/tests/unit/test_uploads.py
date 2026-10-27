"""
Unit tests for Task 3 (manual video upload): endpoint validation (rejects
bad files, accepts good ones), and that the pipeline picks up the
uploaded source correctly. Uses a fake detection backend (no real YOLO
weights required) for the background processing job, same pattern as the
rest of this repo's pipeline tests.
"""
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import backend.api.incident as incident_api
import backend.api.uploads as uploads_api
from backend.config.cameras import _reset_overrides_for_tests, get_camera
from backend.main import app
from vision.detection.detector import Detector, ModelClassConfig


class FakeBackend:
    def infer(self, image, confidence_threshold):
        return [("person", 0.9, (10.0, 10.0, 30.0, 30.0))]


def fake_detector() -> Detector:
    class_config = ModelClassConfig.from_file("configs/model_versions.json")
    return Detector(FakeBackend(), class_config, confidence_threshold=0.5)


@pytest.fixture(autouse=True)
def reset_state():
    uploads_api._reset_for_tests()
    incident_api._reset_for_tests()
    _reset_overrides_for_tests()
    yield
    uploads_api._reset_for_tests()
    incident_api._reset_for_tests()
    _reset_overrides_for_tests()


def make_video_bytes(width, height, frames=3, fps=1.0) -> bytes:
    """Writes a tiny real video to a temp file and returns its bytes —
    genuine video data, not a fabricated stub, so VideoSource validation
    exercises the real decode path."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for i in range(frames):
        writer.write(np.full((height, width, 3), i % 256, dtype=np.uint8))
    writer.release()
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_rejects_unsupported_file_extension():
    client = TestClient(app)
    resp = client.post("/cameras/CAM-01/upload", files={"file": ("scene.txt", b"not a video", "text/plain")})
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_rejects_empty_file():
    client = TestClient(app)
    resp = client.post("/cameras/CAM-01/upload", files={"file": ("scene.mp4", b"", "video/mp4")})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_rejects_corrupt_video_with_valid_extension():
    client = TestClient(app)
    garbage = b"this is not a real mp4 file, just garbage bytes pretending to be one"
    resp = client.post("/cameras/CAM-01/upload", files={"file": ("scene.mp4", garbage, "video/mp4")})
    assert resp.status_code == 400
    assert "Could not read video" in resp.json()["detail"]


def test_rejects_resolution_mismatch_for_camera_with_declared_resolution():
    # CAM-01 declares [720, 1280]; upload something else entirely.
    content = make_video_bytes(width=320, height=240)
    client = TestClient(app)
    resp = client.post("/cameras/CAM-01/upload", files={"file": ("scene.mp4", content, "video/mp4")})
    assert resp.status_code == 400
    assert "does not match" in resp.json()["detail"]


def test_rejects_upload_for_unknown_camera():
    content = make_video_bytes(width=64, height=64)
    client = TestClient(app)
    resp = client.post("/cameras/NOPE/upload", files={"file": ("scene.mp4", content, "video/mp4")})
    assert resp.status_code == 404


def test_accepts_valid_video_matching_declared_resolution():
    content = make_video_bytes(width=720, height=1280, frames=2)
    client = TestClient(app)
    resp = client.post("/cameras/CAM-01/upload", files={"file": ("scene.mp4", content, "video/mp4")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["camera_id"] == "CAM-01"
    assert body["status"] == "processing"
    assert body["resolution"] == [720, 1280]


def test_accepts_any_resolution_for_camera_with_no_declared_resolution():
    # CAM-02 has resolution: null — nothing to mismatch against.
    content = make_video_bytes(width=100, height=100, frames=2)
    client = TestClient(app)
    resp = client.post("/cameras/CAM-02/upload", files={"file": ("scene.mp4", content, "video/mp4")})
    assert resp.status_code == 200
    assert resp.json()["resolution"] == [100, 100]


# ---------------------------------------------------------------------------
# Pipeline picks up the uploaded source
# ---------------------------------------------------------------------------

def test_upload_sets_source_override_picked_up_by_get_camera():
    content = make_video_bytes(width=100, height=100, frames=2)
    uploads_api.handle_upload("CAM-02", "scene.mp4", content, detector=fake_detector())

    camera = get_camera("CAM-02")
    assert camera.source.endswith(".mp4")
    assert "CAM-02_" in camera.source  # the generated upload filename, not the original placeholder


def test_upload_processing_runs_real_pipeline_and_reaches_ready(tmp_path):
    content = make_video_bytes(width=100, height=100, frames=3, fps=5.0)
    job = uploads_api.handle_upload("CAM-02", "scene.mp4", content, detector=fake_detector())
    assert job.status == "processing"

    for _ in range(50):
        job = uploads_api.get_job("CAM-02")
        if job.status in ("ready", "failed"):
            break
        time.sleep(0.05)

    assert job.status == "ready", job.detail
    assert job.ticks_processed > 0

    # And the real Incident State for CAM-02 was actually published — not
    # a fabricated "done" flag with no underlying data.
    state = incident_api.get_current_incident_state("CAM-02")
    assert state is not None
    assert state.camera_id == "CAM-02"


def test_upload_status_endpoint_reports_job_progress():
    content = make_video_bytes(width=100, height=100, frames=2)
    client = TestClient(app)
    client.post("/cameras/CAM-02/upload", files={"file": ("scene.mp4", content, "video/mp4")})

    resp = client.get("/cameras/CAM-02/upload/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["camera_id"] == "CAM-02"
    assert body["status"] in ("processing", "ready", "failed")


def test_upload_status_404_when_no_job_exists():
    client = TestClient(app)
    resp = client.get("/cameras/CAM-01/upload/status")
    assert resp.status_code == 404


def test_failed_processing_job_reports_failed_status_not_fabricated_ready():
    """A detector that raises mid-processing must surface as 'failed', not
    be silently swallowed or reported as successful."""

    class ExplodingBackend:
        def infer(self, image, confidence_threshold):
            raise RuntimeError("simulated inference failure")

    class_config = ModelClassConfig.from_file("configs/model_versions.json")
    exploding_detector = Detector(ExplodingBackend(), class_config, confidence_threshold=0.5)

    content = make_video_bytes(width=100, height=100, frames=2)
    job = uploads_api.handle_upload("CAM-02", "scene.mp4", content, detector=exploding_detector)

    for _ in range(50):
        job = uploads_api.get_job("CAM-02")
        if job.status in ("ready", "failed"):
            break
        time.sleep(0.05)

    assert job.status == "failed"
    assert "simulated inference failure" in job.detail
