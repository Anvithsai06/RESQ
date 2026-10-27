"""
Unit tests for Task 2 (multi-camera): per-camera incident state isolation,
the /incident/aggregate rollup, camera registry loading, and per-camera
API responses — all against real config files (building/cameras.json etc.),
not fabricated data.
"""
import pytest
from fastapi.testclient import TestClient

import backend.api.incident as incident_api
from backend.config.cameras import CameraConfig, get_camera, load_cameras
from backend.main import app
from intelligence.incident.state import IncidentState
from intelligence.priority.engine import PriorityComponentScores, PriorityResult


@pytest.fixture(autouse=True)
def reset_incident_store():
    incident_api._reset_for_tests()
    yield
    incident_api._reset_for_tests()


def make_state(camera_id, priority=10.0, band="normal", people=None, hazards=None, alert_active=False):
    return IncidentState(
        timestamp=0.0, camera_id=camera_id, priority=priority, band=band, trend="stable",
        affected_zones=[], people=people or [], hazards=hazards or [], exits=[], congestion={},
        contributors=[], confidence=1.0, uncertainty=False, notification=None, timeline=[],
        alert_active=alert_active,
    )


# ---------------------------------------------------------------------------
# Camera registry
# ---------------------------------------------------------------------------

def test_load_cameras_reads_real_config():
    cameras = load_cameras()
    ids = {c.camera_id for c in cameras}
    assert "CAM-01" in ids
    assert "CAM-02" in ids


def test_cam01_reports_source_available_cam02_does_not():
    cam01 = get_camera("CAM-01")
    cam02 = get_camera("CAM-02")
    assert cam01.source_available is True
    assert cam02.source_available is False  # honestly unavailable — not fabricated


def test_cam02_has_no_calibrated_zones_or_resolution():
    cam02 = get_camera("CAM-02")
    assert cam02.resolution is None
    assert cam02.covered_zones == []
    assert cam02.covered_exits == []


def test_get_camera_returns_none_for_unknown_id():
    assert get_camera("CAM-DOES-NOT-EXIST") is None


def test_each_camera_has_its_own_zones_and_exits_config_path():
    cam01 = get_camera("CAM-01")
    cam02 = get_camera("CAM-02")
    assert cam01.zones_config_path != cam02.zones_config_path
    assert cam01.exits_config_path != cam02.exits_config_path


# ---------------------------------------------------------------------------
# Per-camera incident state isolation
# ---------------------------------------------------------------------------

def test_publishing_two_cameras_does_not_cross_contaminate():
    incident_api.publish_incident_state(make_state("CAM-01", priority=20.0))
    incident_api.publish_incident_state(make_state("CAM-02", priority=80.0))

    cam01 = incident_api.get_current_incident_state("CAM-01")
    cam02 = incident_api.get_current_incident_state("CAM-02")

    assert cam01.priority == 20.0
    assert cam02.priority == 80.0


def test_republishing_one_camera_does_not_affect_another():
    incident_api.publish_incident_state(make_state("CAM-01", priority=20.0))
    incident_api.publish_incident_state(make_state("CAM-02", priority=80.0))

    incident_api.publish_incident_state(make_state("CAM-01", priority=95.0))

    assert incident_api.get_current_incident_state("CAM-01").priority == 95.0
    assert incident_api.get_current_incident_state("CAM-02").priority == 80.0  # untouched


def test_default_camera_lookup_matches_cam01():
    incident_api.publish_incident_state(make_state("CAM-01", priority=42.0))
    assert incident_api.get_current_incident_state().priority == 42.0  # no arg == CAM-01


def test_unpublished_camera_returns_none():
    incident_api.publish_incident_state(make_state("CAM-01", priority=1.0))
    assert incident_api.get_current_incident_state("CAM-02") is None


def test_get_all_incident_states_only_includes_reporting_cameras():
    incident_api.publish_incident_state(make_state("CAM-01", priority=1.0))
    all_states = incident_api.get_all_incident_states()
    assert set(all_states.keys()) == {"CAM-01"}  # CAM-02 never fabricated in


# ---------------------------------------------------------------------------
# Aggregate rollup
# ---------------------------------------------------------------------------

def test_aggregate_with_no_cameras_reporting():
    client = TestClient(app)
    resp = client.get("/incident/aggregate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cameras_reporting"] == 0
    assert body["highest_priority"] is None
    assert body["cameras"] == []


def test_aggregate_picks_highest_priority_across_cameras():
    incident_api.publish_incident_state(make_state("CAM-01", priority=30.0, band="moderate"))
    incident_api.publish_incident_state(make_state("CAM-02", priority=75.0, band="high"))

    client = TestClient(app)
    body = client.get("/incident/aggregate").json()

    assert body["cameras_reporting"] == 2
    assert body["highest_priority"] == 75.0
    assert body["highest_priority_camera_id"] == "CAM-02"
    assert body["cameras"][0]["camera_id"] == "CAM-02"  # sorted by priority desc


def test_aggregate_sums_people_across_cameras():
    person_a = _person(1)
    person_b = _person(2)
    person_c = _person(3)
    incident_api.publish_incident_state(make_state("CAM-01", people=[person_a, person_b]))
    incident_api.publish_incident_state(make_state("CAM-02", people=[person_c]))

    client = TestClient(app)
    body = client.get("/incident/aggregate").json()

    assert body["total_people"] == 3


def test_aggregate_combines_hazard_classes_from_all_cameras():
    incident_api.publish_incident_state(make_state("CAM-01", hazards=[_hazard("fire")]))
    incident_api.publish_incident_state(make_state("CAM-02", hazards=[_hazard("smoke")]))

    client = TestClient(app)
    body = client.get("/incident/aggregate").json()

    assert body["combined_hazard_classes"] == ["fire", "smoke"]


def test_aggregate_any_alert_active_true_if_any_camera_latched():
    incident_api.publish_incident_state(make_state("CAM-01", alert_active=False))
    incident_api.publish_incident_state(make_state("CAM-02", alert_active=True))

    client = TestClient(app)
    body = client.get("/incident/aggregate").json()

    assert body["any_alert_active"] is True


def _person(track_id):
    from intelligence.incident.state import IncidentPerson

    return IncidentPerson(
        track_id=track_id, class_name="person", current_zone=None, confidence=0.9,
        dwell_time=0.0, movement_direction=None,
    )


def _hazard(class_name):
    from intelligence.incident.state import IncidentHazard

    return IncidentHazard(class_name=class_name, presence=True, confidence=0.8, persistence_frames=5)


# ---------------------------------------------------------------------------
# API routes — /incident/camera/{id}, /incident/all
# ---------------------------------------------------------------------------

def test_incident_camera_route_returns_404_for_camera_with_no_data():
    client = TestClient(app)
    resp = client.get("/incident/camera/CAM-02")
    assert resp.status_code == 404


def test_incident_camera_route_returns_that_cameras_state():
    incident_api.publish_incident_state(make_state("CAM-01", priority=11.0))
    incident_api.publish_incident_state(make_state("CAM-02", priority=22.0))

    client = TestClient(app)
    body = client.get("/incident/camera/CAM-02").json()

    assert body["camera_id"] == "CAM-02"
    assert body["priority"] == 22.0


def test_incident_all_route_lists_every_reporting_camera():
    incident_api.publish_incident_state(make_state("CAM-01", priority=11.0))
    incident_api.publish_incident_state(make_state("CAM-02", priority=22.0))

    client = TestClient(app)
    body = client.get("/incident/all").json()

    assert set(body.keys()) == {"CAM-01", "CAM-02"}


def test_current_route_stays_cam01_for_backward_compatibility():
    incident_api.publish_incident_state(make_state("CAM-01", priority=5.0))
    incident_api.publish_incident_state(make_state("CAM-02", priority=99.0))

    client = TestClient(app)
    body = client.get("/incident/current").json()

    assert body["camera_id"] == "CAM-01"
    assert body["priority"] == 5.0


# ---------------------------------------------------------------------------
# Config API — /config/cameras, per-camera zones/exits
# ---------------------------------------------------------------------------

def test_config_cameras_route_lists_both_cameras_with_availability():
    client = TestClient(app)
    body = client.get("/config/cameras").json()
    by_id = {c["camera_id"]: c for c in body}

    assert by_id["CAM-01"]["source_available"] is True
    assert by_id["CAM-02"]["source_available"] is False


def test_config_camera_zones_route_returns_cam02_empty_zone_list():
    client = TestClient(app)
    body = client.get("/config/cameras/CAM-02/zones").json()
    assert body["zones"] == []


def test_config_camera_zones_route_404s_for_unknown_camera():
    client = TestClient(app)
    resp = client.get("/config/cameras/NOPE/zones")
    assert resp.status_code == 404
