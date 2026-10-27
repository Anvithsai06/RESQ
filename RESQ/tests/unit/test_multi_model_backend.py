"""
Unit tests for the two-model detection backend (person + fire/smoke).

Uses fake YoloBackends for the merge/filtering tests — same hermetic
pattern as tests/unit/test_detector.py — so these don't require the real
downloaded weights. The "missing model files" test and the real-weights
inference smoke test are separate (see the smoke test run in the session
log / README note), since CI environments won't have the large gitignored
.pt files checked in.
"""
import pytest

from vision.detection.detector import (
    Detector,
    ModelClassConfig,
    MultiModelBackend,
    UltralyticsBackend,
    create_multi_model_detector,
)
from vision.video.ingestion import Frame
import numpy as np


class FakeBackend:
    def __init__(self, raw_detections):
        self._raw_detections = raw_detections

    def infer(self, image, confidence_threshold):
        return self._raw_detections


def make_frame():
    return Frame(
        image=np.zeros((10, 10, 3), dtype=np.uint8),
        frame_index=0,
        timestamp=1.0,
        camera_id="CAM-01",
        source_fps=10.0,
        frame_width=10,
        frame_height=10,
    )


@pytest.fixture
def class_config():
    return ModelClassConfig(validated_classes={"person"}, experimental_classes={"fire", "smoke"})


def test_multi_model_backend_merges_person_and_hazard_output():
    person_backend = FakeBackend([("person", 0.9, (0.0, 0.0, 10.0, 10.0))])
    hazard_backend = FakeBackend(
        [("fire", 0.85, (20.0, 20.0, 40.0, 40.0)), ("smoke", 0.7, (50.0, 50.0, 70.0, 70.0))]
    )
    backend = MultiModelBackend(person_backend, hazard_backend)

    raw = backend.infer(np.zeros((10, 10, 3), dtype=np.uint8), confidence_threshold=0.5)

    assert raw == [
        ("person", 0.9, (0.0, 0.0, 10.0, 10.0)),
        ("fire", 0.85, (20.0, 20.0, 40.0, 40.0)),
        ("smoke", 0.7, (50.0, 50.0, 70.0, 70.0)),
    ]


def test_class_names_preserved_through_merge_and_detector(class_config):
    person_backend = FakeBackend([("person", 0.9, (0.0, 0.0, 10.0, 10.0))])
    hazard_backend = FakeBackend([("fire", 0.9, (20.0, 20.0, 40.0, 40.0))])
    detector = Detector(MultiModelBackend(person_backend, hazard_backend), class_config, confidence_threshold=0.5)

    detections = detector.detect(make_frame())
    class_names = {d.class_name for d in detections}

    assert class_names == {"person", "fire"}
    person_det = next(d for d in detections if d.class_name == "person")
    fire_det = next(d for d in detections if d.class_name == "fire")
    assert person_det.validated is True  # "person" is in validated_classes
    assert fire_det.validated is False  # "fire" is only in experimental_classes


def test_existing_class_filtering_still_applies_to_merged_output(class_config):
    # person backend outputs an allowed class + an unlisted one; hazard
    # backend outputs an allowed class below threshold.
    person_backend = FakeBackend(
        [("person", 0.9, (0.0, 0.0, 10.0, 10.0)), ("dog", 0.99, (0.0, 0.0, 10.0, 10.0))]
    )
    hazard_backend = FakeBackend([("smoke", 0.2, (0.0, 0.0, 10.0, 10.0))])  # below 0.5 threshold
    detector = Detector(MultiModelBackend(person_backend, hazard_backend), class_config, confidence_threshold=0.5)

    detections = detector.detect(make_frame())

    assert [d.class_name for d in detections] == ["person"]


def test_multi_model_backend_with_no_hazard_detections():
    person_backend = FakeBackend([("person", 0.9, (0.0, 0.0, 10.0, 10.0))])
    hazard_backend = FakeBackend([])
    backend = MultiModelBackend(person_backend, hazard_backend)

    raw = backend.infer(np.zeros((10, 10, 3), dtype=np.uint8), confidence_threshold=0.5)

    assert raw == [("person", 0.9, (0.0, 0.0, 10.0, 10.0))]


# The three tests below construct a real UltralyticsBackend, which lazily
# imports `ultralytics` — skip cleanly (not error) in an environment where
# it isn't installed, same hermetic philosophy as the rest of this suite.
ultralytics = pytest.importorskip("ultralytics")


def test_missing_person_model_file_raises_clear_error():
    with pytest.raises(FileNotFoundError):
        UltralyticsBackend("models/yolo/does_not_exist_person.pt")


def test_missing_hazard_model_file_raises_clear_error():
    with pytest.raises(FileNotFoundError):
        UltralyticsBackend("models/yolo/does_not_exist_hazard.pt")


def test_create_multi_model_detector_propagates_missing_file_error():
    with pytest.raises(FileNotFoundError):
        create_multi_model_detector(
            person_model_path="models/yolo/does_not_exist_person.pt",
            hazard_model_path="models/yolo/fire_smoke.pt",
            model_versions_path="configs/model_versions.json",
            confidence_threshold=0.5,
        )
