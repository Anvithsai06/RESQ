"""
Dev-only demo seed — NOT the real pipeline.

Runs a short synthetic escalating scenario through the already-built
intelligence stack (zone engine, temporal engine, exit state machine,
priority engine, incident state builder) so the dashboard (Phase 13) has
real, evolving Incident State to render locally — without needing YOLO
weights, the demo video, or ByteTrack running. Phase 14 replaces this with
the real video-driven pipeline.

Bboxes below are in CAM-01's real 720x1280 image space and are chosen so
their bottom-center lands inside building/zones.json's DANGER-A polygon and
building/exits.json's EXIT-B polygon — every number the intelligence stack
produces (occupancy, persistence, priority, uncertainty) is genuinely
computed from this synthetic input, not hardcoded. Keep these in sync if
those polygons are ever re-calibrated.

Opt-in only — see backend/main.py's lifespan: set
RESQ_DEV_SEED_DEMO_INCIDENT=true before starting uvicorn to run this in the
same process as the API server (required, since the incident store in
backend/api/incident.py is in-memory and per-process).
"""
from __future__ import annotations

import time

from backend.api.incident import publish_incident_state
from intelligence.incident.state import IncidentStateBuilder
from intelligence.priority.engine import PriorityEngine
from intelligence.temporal.engine import TemporalEngine
from intelligence.temporal.exit_state import ExitStateEngine
from vision.detection.detector import Detection
from vision.tracking.byte_tracker import Track
from vision.zones.engine import ZoneEngine

CAMERA_ID = "CAM-01"


def _track(track_id, bbox, class_name="person", confidence=0.9):
    return Track(
        track_id=track_id, class_name=class_name, bbox=bbox, confidence=confidence,
        first_seen=0.0, last_seen=0.0, trajectory=[], camera_id=CAMERA_ID,
    )


def _detection(class_name, confidence, timestamp):
    return Detection(
        class_name=class_name, confidence=confidence, bbox=(200.0, 600.0, 280.0, 700.0),
        timestamp=timestamp, camera_id=CAMERA_ID, validated=False,
    )


def _build_ticks() -> list[tuple[float, list[Track], list[Detection]]]:
    danger_people = [
        _track(1, (140, 650, 190, 750)),
        _track(2, (240, 660, 290, 760)),
        _track(3, (340, 650, 390, 755)),
    ]
    exit_person = _track(4, (480, 950, 530, 1050))

    ticks: list[tuple[float, list[Track], list[Detection]]] = [
        (0.0, [], []),
        (1.0, [], []),
        (2.0, danger_people[:1], []),
        (3.0, danger_people[:2], [_detection("fire", 0.85, 3.0)]),
        (4.0, danger_people[:3], [_detection("fire", 0.9, 4.0)]),
        (5.0, danger_people + [exit_person], [_detection("fire", 0.92, 5.0)]),
    ]
    for t in range(6, 12):
        ticks.append((float(t), danger_people + [exit_person], [_detection("fire", 0.92, float(t))]))
    return ticks


def run(sleep_seconds: float = 1.5) -> None:
    zone_engine = ZoneEngine.from_files("building/zones.json", "building/exits.json", camera_id=CAMERA_ID)
    temporal_engine = TemporalEngine.from_thresholds_file("configs/thresholds.json", camera_id=CAMERA_ID)
    exit_state_engine = ExitStateEngine.from_config_files("configs/thresholds.json", "building/exits.json")
    priority_engine = PriorityEngine.from_config_files(
        "configs/thresholds.json", "configs/model_versions.json", "building/zones.json"
    )
    incident_builder = IncidentStateBuilder()

    for timestamp, tracks, detections in _build_ticks():
        zone_state = zone_engine.update(tracks, timestamp)
        temporal_state = temporal_engine.update(tracks, detections, zone_state, timestamp)
        exit_states = exit_state_engine.update(temporal_state.exits, tracks, zone_state.track_exit)
        priority_result = priority_engine.update(zone_state, temporal_state, exit_states, tracks, timestamp)
        incident_state = incident_builder.update(zone_state, temporal_state, exit_states, priority_result, tracks, timestamp)

        publish_incident_state(incident_state)
        print(
            f"[dev-seed] t={timestamp:5.1f}  priority={incident_state.priority:5.1f}  "
            f"band={incident_state.band:8s}  trend={incident_state.trend}"
        )
        time.sleep(sleep_seconds)

    print("[dev-seed] scenario finished — holding at final state.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    run()
