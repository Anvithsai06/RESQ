"""
Unit tests for YOLO detection filtering/postprocessing (WORKFLOW.md Phase 3).

Uses a fake YoloBackend so these tests don't require model weights or the
ultralytics package to be installed — only the Detector's filtering logic
(confidence threshold, class allowlist, validated flag) is under test.
"""
import numpy as np
import pytest

from vision.detection.detector import Detection, Detector, ModelClassConfig
from vision.video.ingestion import Frame


class FakeBackend:
    """Returns a canned list of raw (class_name, confidence, bbox) tuples,
    ignoring the actual image content."""

    def __init__(self, raw_detections):
        self._raw_detections = raw_detections

    def infer(self, image, confidence_threshold):
        return self._raw_detections


def make_frame(timestamp=1.5, camera_id="CAM-01"):
    return Frame(
        image=np.zeros((10, 10, 3), dtype=np.uint8),
        frame_index=15,
        timestamp=timestamp,
        camera_id=camera_id,
        source_fps=10.0,
        frame_width=10,
        frame_height=10,
    )


@pytest.fixture
def class_config():
    return ModelClassConfig(validated_classes={"person"}, experimental_classes={"fire", "smoke"})


def test_returns_detection_for_validated_class(class_config):
    backend = FakeBackend([("person", 0.94, (10.0, 20.0, 110.0, 220.0))])
    detector = Detector(backend, class_config, confidence_threshold=0.5)

    detections = detector.detect(make_frame())

    assert len(detections) == 1
    d = detections[0]
    assert isinstance(d, Detection)
    assert d.class_name == "person"
    assert d.confidence == 0.94
    assert d.bbox == (10.0, 20.0, 110.0, 220.0)
    assert d.timestamp == 1.5
    assert d.camera_id == "CAM-01"
    assert d.validated is True


def test_experimental_class_flagged_not_validated(class_config):
    backend = FakeBackend([("fire", 0.75, (0.0, 0.0, 50.0, 50.0))])
    detector = Detector(backend, class_config, confidence_threshold=0.5)

    detections = detector.detect(make_frame())

    assert len(detections) == 1
    assert detections[0].class_name == "fire"
    assert detections[0].validated is False


def test_unlisted_class_is_dropped(class_config):
    backend = FakeBackend([("dog", 0.99, (0.0, 0.0, 50.0, 50.0))])
    detector = Detector(backend, class_config, confidence_threshold=0.5)

    detections = detector.detect(make_frame())

    assert detections == []


def test_low_confidence_detection_is_dropped(class_config):
    backend = FakeBackend([("person", 0.2, (0.0, 0.0, 50.0, 50.0))])
    detector = Detector(backend, class_config, confidence_threshold=0.5)

    detections = detector.detect(make_frame())

    assert detections == []


def test_mixed_batch_filters_correctly(class_config):
    backend = FakeBackend(
        [
            ("person", 0.94, (0.0, 0.0, 10.0, 10.0)),
            ("dog", 0.99, (0.0, 0.0, 10.0, 10.0)),
            ("fire", 0.3, (0.0, 0.0, 10.0, 10.0)),  # below threshold
            ("smoke", 0.6, (0.0, 0.0, 10.0, 10.0)),
        ]
    )
    detector = Detector(backend, class_config, confidence_threshold=0.5)

    detections = detector.detect(make_frame())
    class_names = {d.class_name for d in detections}

    assert class_names == {"person", "smoke"}


def test_model_class_config_from_real_file():
    config = ModelClassConfig.from_file("configs/model_versions.json")

    assert config.is_validated("person")
    assert config.is_allowed("fire")
    assert not config.is_validated("fire")
    assert not config.is_allowed("dog")
