"""
Unit tests for the zone engine (WORKFLOW.md Phase 6): polygon membership,
occupancy, danger-zone occupancy, exit occupancy, and enter/exit events.
"""
from vision.tracking.byte_tracker import Track
from vision.zones.engine import Exit, Zone, ZoneEngine, ZoneMembershipEvent, reference_point


def make_track(track_id, bbox, class_name="person"):
    return Track(
        track_id=track_id,
        class_name=class_name,
        bbox=bbox,
        confidence=0.9,
        first_seen=0.0,
        last_seen=0.0,
        trajectory=[],
        camera_id="CAM-01",
    )


DANGER_A = Zone(id="DANGER-A", type="danger", label="Danger Zone A", polygon=[(0, 0), (100, 0), (100, 100), (0, 100)])
SAFE = Zone(id="SAFE-1", type="safe_observation", label="Safe", polygon=[(200, 0), (300, 0), (300, 100), (200, 100)])
EXIT_A = Exit(id="EXIT-A", label="Exit A", polygon=[(400, 0), (500, 0), (500, 100), (400, 100)], trusted=True)
EXIT_UNTRUSTED = Exit(
    id="EXIT-X", label="Untrusted door", polygon=[(600, 0), (700, 0), (700, 100), (600, 100)], trusted=False
)


def test_reference_point_is_bbox_bottom_center():
    assert reference_point((10.0, 20.0, 30.0, 60.0)) == (20.0, 60.0)


def test_track_inside_danger_zone_increments_occupancy_and_danger_count():
    engine = ZoneEngine(zones=[DANGER_A, SAFE], exits=[EXIT_A], camera_id="CAM-01")
    track = make_track(1, bbox=(40, 40, 60, 80))  # bottom-center (50, 80) is inside DANGER-A

    state = engine.update([track], timestamp=1.0)

    assert state.track_zone[1] == "DANGER-A"
    assert state.zone_occupancy["DANGER-A"] == 1
    assert state.zone_occupancy["SAFE-1"] == 0
    assert state.danger_zone_occupancy == 1
    assert track.current_zone == "DANGER-A"


def test_track_outside_all_zones_has_none_zone():
    engine = ZoneEngine(zones=[DANGER_A, SAFE], exits=[], camera_id="CAM-01")
    track = make_track(1, bbox=(900, 900, 950, 950))

    state = engine.update([track], timestamp=1.0)

    assert state.track_zone[1] is None
    assert state.danger_zone_occupancy == 0


def test_enter_event_emitted_on_first_frame_in_zone():
    engine = ZoneEngine(zones=[DANGER_A], exits=[], camera_id="CAM-01")
    track = make_track(1, bbox=(40, 40, 60, 80))

    state = engine.update([track], timestamp=1.0)

    assert len(state.events) == 1
    event = state.events[0]
    assert event.track_id == 1
    assert event.zone_id == "DANGER-A"
    assert event.event_type == "enter"


def test_move_between_zones_emits_exit_then_enter():
    engine = ZoneEngine(zones=[DANGER_A, SAFE], exits=[], camera_id="CAM-01")
    track = make_track(1, bbox=(40, 40, 60, 80))  # inside DANGER-A
    engine.update([track], timestamp=1.0)

    track.bbox = (240, 40, 260, 80)  # now inside SAFE-1
    state = engine.update([track], timestamp=2.0)

    event_types = [(e.zone_id, e.event_type) for e in state.events]
    assert ("DANGER-A", "exit") in event_types
    assert ("SAFE-1", "enter") in event_types
    assert state.zone_occupancy["DANGER-A"] == 0
    assert state.zone_occupancy["SAFE-1"] == 1


def test_track_disappearing_emits_exit_event():
    engine = ZoneEngine(zones=[DANGER_A], exits=[], camera_id="CAM-01")
    track = make_track(1, bbox=(40, 40, 60, 80))
    engine.update([track], timestamp=1.0)

    state = engine.update([], timestamp=2.0)  # track no longer present (lost)

    assert state.events == [ZoneMembershipEvent(track_id=1, zone_id="DANGER-A", event_type="exit", timestamp=2.0)]
    assert state.zone_occupancy["DANGER-A"] == 0


def test_exit_occupancy_counts_only_trusted_exits():
    engine = ZoneEngine(zones=[], exits=[EXIT_A, EXIT_UNTRUSTED], camera_id="CAM-01")

    assert [e.id for e in engine.exits] == ["EXIT-A"]

    track_in_exit_a = make_track(1, bbox=(440, 40, 460, 80))
    track_in_untrusted_door = make_track(2, bbox=(640, 40, 660, 80))

    state = engine.update([track_in_exit_a, track_in_untrusted_door], timestamp=1.0)

    assert state.exit_occupancy == {"EXIT-A": 1}
    assert state.track_exit[1] == "EXIT-A"
    assert state.track_exit[2] is None  # untrusted door never counts


def test_multiple_people_in_same_zone_counted_correctly():
    engine = ZoneEngine(zones=[DANGER_A], exits=[], camera_id="CAM-01")
    tracks = [make_track(1, bbox=(10, 10, 30, 50)), make_track(2, bbox=(50, 50, 70, 90))]

    state = engine.update(tracks, timestamp=1.0)

    assert state.zone_occupancy["DANGER-A"] == 2
    assert state.danger_zone_occupancy == 2


def test_zone_and_exit_load_from_real_building_config():
    zones = Zone.from_file("building/zones.json")
    exits = Exit.from_file("building/exits.json")

    zone_ids = {z.id for z in zones}
    exit_ids = {e.id for e in exits}

    assert "DANGER-A" in zone_ids
    assert "EXIT-A" in exit_ids
    assert all(e.trusted for e in exits)  # matches building/exits.json fixture
