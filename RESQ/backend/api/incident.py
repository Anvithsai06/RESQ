"""
Incident State API — WORKFLOW.md Phase 13, generalized for multi-camera.

Serves Incident State (intelligence/incident/state.py) per camera. This
module owns a simple in-memory "latest state per camera" store;
`publish_incident_state()` is the seam Phase 14's pipeline(s) — one per
camera — write into on each tick.

`GET /incident/current` is kept exactly as it always was (single, default
camera) for backward compatibility with anything built against the
original single-camera API. Multi-camera consumers use the new
`/camera/{camera_id}`, `/all`, and `/aggregate` routes below.

No history/DB-backing here — the `incidents` table (supabase/migrations)
and any persistence beyond "the current snapshot per camera" is Phase 14
integration work, once a live Supabase project is configured.
"""
from __future__ import annotations

import dataclasses
import threading

from fastapi import APIRouter, HTTPException

from intelligence.incident.state import IncidentState

router = APIRouter()

DEFAULT_CAMERA_ID = "CAM-01"  # what GET /current means, for backward compatibility

_lock = threading.Lock()
_incident_by_camera: dict[str, IncidentState] = {}


def publish_incident_state(state: IncidentState) -> None:
    """Called once per tick by whatever is running that camera's pipeline
    (real or demo-seeded) to make a new Incident State visible to the
    dashboard. Keyed by `state.camera_id` — each camera's pipeline
    publishes independently and cannot see or affect another camera's state."""
    with _lock:
        _incident_by_camera[state.camera_id] = state


def get_current_incident_state(camera_id: str = DEFAULT_CAMERA_ID) -> IncidentState | None:
    with _lock:
        return _incident_by_camera.get(camera_id)


def get_all_incident_states() -> dict[str, IncidentState]:
    with _lock:
        return dict(_incident_by_camera)


def _reset_for_tests() -> None:
    """Test-only: clears the store between test cases (it's process-global
    module state, otherwise tests would leak into each other)."""
    global _incident_by_camera
    with _lock:
        _incident_by_camera = {}


@router.get("/current")
def get_current_incident():
    """Unchanged single-camera route — always means DEFAULT_CAMERA_ID."""
    state = get_current_incident_state(DEFAULT_CAMERA_ID)
    if state is None:
        raise HTTPException(status_code=404, detail="No incident data yet")
    return dataclasses.asdict(state)


@router.get("/camera/{camera_id}")
def get_camera_incident(camera_id: str):
    state = get_current_incident_state(camera_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"No incident data yet for camera {camera_id!r}")
    return dataclasses.asdict(state)


@router.get("/all")
def get_all_incidents():
    """Every camera currently reporting, keyed by camera_id. A camera with
    no configured/running pipeline simply never appears here — never a
    fabricated entry."""
    return {camera_id: dataclasses.asdict(state) for camera_id, state in get_all_incident_states().items()}


@router.get("/aggregate")
def get_aggregate_incident():
    """Building-wide rollup across every currently-reporting camera. Only
    ever summarizes real per-camera Incident States already published —
    computes nothing a camera hasn't itself already reported."""
    states = get_all_incident_states()

    if not states:
        return {
            "cameras_reporting": 0,
            "highest_priority": None,
            "highest_priority_camera_id": None,
            "total_people": 0,
            "combined_hazard_classes": [],
            "any_alert_active": False,
            "any_uncertainty": False,
            "cameras": [],
        }

    highest = max(states.values(), key=lambda s: s.priority)
    hazard_classes = sorted({h.class_name for s in states.values() for h in s.hazards if h.presence})

    return {
        "cameras_reporting": len(states),
        "highest_priority": highest.priority,
        "highest_priority_camera_id": highest.camera_id,
        "total_people": sum(len(s.people) for s in states.values()),
        "combined_hazard_classes": hazard_classes,
        "any_alert_active": any(s.alert_active for s in states.values()),
        "any_uncertainty": any(s.uncertainty for s in states.values()),
        "cameras": [
            {
                "camera_id": s.camera_id,
                "priority": s.priority,
                "band": s.band,
                "people_count": len(s.people),
                "hazard_count": sum(1 for h in s.hazards if h.presence),
                "alert_active": s.alert_active,
            }
            for s in sorted(states.values(), key=lambda s: s.priority, reverse=True)
        ],
    }
