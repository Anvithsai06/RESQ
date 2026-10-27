"""
Integration test for the real Phase 14 pipeline (backend/pipeline.py):

    Video -> Detection -> Tracking -> Zone -> Temporal -> Exit State ->
    Priority -> Incident State -> Notification -> Dashboard store

No YOLO weights are committed to this repo, so `run_pipeline` is exercised
with an injected fake detection backend (same pattern as
tests/integration/test_vertical_slice.py) — this proves the wiring between
every real phase's implementation is correct, not that real YOLO inference
works (that needs actual weights + `ultralytics`, per WORKFLOW.md Phase 3).

Bboxes are chosen so their bottom-center lands inside the real
building/zones.json DANGER-A polygon and building/exits.json EXIT-B
polygon, with enough people/hazard confidence/exit occupancy that priority
genuinely computes past the critical threshold and stays there long enough
(configs/thresholds.json: critical_priority_threshold=60, persistence=10s)
for a real notification dispatch to fire — nothing about the outcome is
hardcoded.
"""
import cv2
import numpy as np
import pytest

import backend.api.incident as incident_api
from backend.pipeline import run_pipeline
from vision.detection.detector import Detector, ModelClassConfig

FPS = 1.0
WIDTH, HEIGHT = 64, 64
# Priority crosses critical (60, post-Task-1) at t=2 and holds; with a 10s
# persistence requirement, the notification fires exactly at t=12 (empirically
# traced, not hand-calculated — see the trace script referenced in the Task 1
# report). 13 frames (0..12) means the *last* published tick is the one where
# it actually fires, so the test can assert "sent" rather than the (equally
# correct) subsequent "suppressed_cooldown" a longer run would end on.
TOTAL_FRAMES = 13


class FakeCriticalSceneBackend:
    """6 people in DANGER-A (saturates people-in-danger + congestion), a
    steadily-persisting "fire" hazard, and one person in EXIT-B from frame
    0 (so it crosses the 5s obstruction-persistence threshold partway
    through).

    Bboxes are in CAM-01's real 720x1280 image space and are positioned so
    their bottom-center (the point ZoneEngine actually tests) falls inside
    the real building/zones.json DANGER-A and building/exits.json EXIT-B
    polygons — keep these in sync if those polygons are ever re-calibrated.
    """

    def infer(self, image, confidence_threshold):
        danger_people = [
            ("person", 0.95, (120.0, 650.0, 160.0, 750.0)),
            ("person", 0.95, (180.0, 650.0, 220.0, 750.0)),
            ("person", 0.95, (240.0, 650.0, 280.0, 750.0)),
            ("person", 0.95, (300.0, 650.0, 340.0, 750.0)),
            ("person", 0.95, (360.0, 650.0, 400.0, 750.0)),
            ("person", 0.95, (420.0, 660.0, 460.0, 760.0)),
        ]
        exit_occupant = ("person", 0.95, (480.0, 950.0, 520.0, 1050.0))
        fire = ("fire", 1.0, (200.0, 600.0, 280.0, 700.0))
        return danger_people + [exit_occupant, fire]


@pytest.fixture(autouse=True)
def reset_incident_store():
    incident_api._reset_for_tests()
    yield
    incident_api._reset_for_tests()


@pytest.fixture
def synthetic_video(tmp_path):
    video_path = tmp_path / "synthetic.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    for i in range(TOTAL_FRAMES):
        frame = np.full((HEIGHT, WIDTH, 3), fill_value=i % 256, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return video_path


def test_pipeline_reaches_critical_and_dispatches_notification(synthetic_video):
    class_config = ModelClassConfig.from_file("configs/model_versions.json")
    detector = Detector(FakeCriticalSceneBackend(), class_config, confidence_threshold=0.5)

    run_pipeline(detector, camera_id="CAM-01", video_path=synthetic_video, sample_rate=1)

    state = incident_api.get_current_incident_state()
    assert state is not None

    assert state.priority == pytest.approx(100.0, abs=0.5)
    assert state.band == "critical"
    assert set(state.affected_zones) == {"DANGER-A"}
    assert any(e.exit_id == "EXIT-B" and e.state == "OBSTRUCTED" for e in state.exits)
    assert state.uncertainty is True  # "fire" is still an experimental (unvalidated) class

    assert state.notification.status == "sent"
    assert state.notification.recipient_name is not None
    assert "Fire" in state.notification.recipient_name
    assert state.alert_active is True  # Task 1.4: latched active the instant it fires

    person_enter_events = [
        e for e in state.timeline
        if e.event_type == "zone_enter"
        and e.payload.get("zone_id") == "DANGER-A"
        and e.payload.get("class_name") == "person"
    ]
    assert len(person_enter_events) == 6  # one per person entering DANGER-A
    assert all(e.description.startswith("Person #") for e in person_enter_events)

    # ByteTrack also tracks the hazard, so the fire entering DANGER-A is a
    # legitimate timeline event — but it must be labelled as fire, not as a person.
    fire_enter_events = [
        e for e in state.timeline
        if e.event_type == "zone_enter" and e.payload.get("class_name") == "fire"
    ]
    assert all("Person" not in e.description for e in fire_enter_events)

    # And the hazard track must never leak into the dashboard's people list.
    assert all(p.class_name == "person" for p in state.people)
