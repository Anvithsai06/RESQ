"""
Unit tests for the temporal scene-state engine (WORKFLOW.md Phase 7):
entity dwell/movement, zone occupancy/congestion/entry-exit counts, hazard
presence/persistence, and exit occupancy persistence.
"""
from intelligence.temporal.engine import TemporalEngine
from vision.detection.detector import Detection
from vision.tracking.byte_tracker import Track
from vision.zones.engine import ZoneMembershipEvent, ZoneState


def make_track(track_id, bbox, first_seen=0.0, last_seen=0.0, class_name="person"):
    return Track(
        track_id=track_id,
        class_name=class_name,
        bbox=bbox,
        confidence=0.9,
        first_seen=first_seen,
        last_seen=last_seen,
        trajectory=[],
        camera_id="CAM-01",
    )


def make_detection(class_name, confidence, timestamp=0.0):
    return Detection(
        class_name=class_name,
        confidence=confidence,
        bbox=(0, 0, 10, 10),
        timestamp=timestamp,
        camera_id="CAM-01",
        validated=False,
    )


def zone_state(timestamp, track_zone, zone_occupancy, exit_occupancy=None, events=None, track_exit=None):
    return ZoneState(
        timestamp=timestamp,
        camera_id="CAM-01",
        track_zone=track_zone,
        track_exit=track_exit or {},
        zone_occupancy=zone_occupancy,
        exit_occupancy=exit_occupancy or {},
        danger_zone_occupancy=0,
        events=events or [],
    )


def test_entity_dwell_time_accumulates_while_in_same_zone():
    engine = TemporalEngine(camera_id="CAM-01")
    track = make_track(1, bbox=(0, 0, 10, 10), first_seen=0.0, last_seen=0.0)

    zs1 = zone_state(0.0, {1: "Z1"}, {"Z1": 1}, events=[ZoneMembershipEvent(1, "Z1", "enter", 0.0)])
    state1 = engine.update([track], [], zs1, timestamp=0.0)
    assert state1.entities[1].dwell_time == 0.0

    track.last_seen = 5.0
    zs2 = zone_state(5.0, {1: "Z1"}, {"Z1": 1})
    state2 = engine.update([track], [], zs2, timestamp=5.0)
    assert state2.entities[1].dwell_time == 5.0
    assert state2.entities[1].first_seen == 0.0


def test_entity_dwell_time_resets_on_zone_change():
    engine = TemporalEngine(camera_id="CAM-01")
    track = make_track(1, bbox=(0, 0, 10, 10))

    zs1 = zone_state(0.0, {1: "Z1"}, {"Z1": 1, "Z2": 0}, events=[ZoneMembershipEvent(1, "Z1", "enter", 0.0)])
    engine.update([track], [], zs1, timestamp=0.0)

    zs2 = zone_state(5.0, {1: "Z1"}, {"Z1": 1, "Z2": 0})
    engine.update([track], [], zs2, timestamp=5.0)

    zs3 = zone_state(
        6.0, {1: "Z2"}, {"Z1": 0, "Z2": 1},
        events=[ZoneMembershipEvent(1, "Z1", "exit", 6.0), ZoneMembershipEvent(1, "Z2", "enter", 6.0)],
    )
    state3 = engine.update([track], [], zs3, timestamp=6.0)

    assert state3.entities[1].current_zone == "Z2"
    assert state3.entities[1].previous_zone == "Z1"
    assert state3.entities[1].dwell_time == 0.0


def test_movement_direction_none_on_first_observation_then_computed():
    engine = TemporalEngine(camera_id="CAM-01")
    track = make_track(1, bbox=(0, 0, 10, 10))

    zs1 = zone_state(0.0, {1: None}, {})
    state1 = engine.update([track], [], zs1, timestamp=0.0)
    assert state1.entities[1].movement_direction is None

    track.bbox = (20, 20, 30, 30)  # moved down-right
    zs2 = zone_state(1.0, {1: None}, {})
    state2 = engine.update([track], [], zs2, timestamp=1.0)
    assert state2.entities[1].movement_direction == "down-right"


def test_movement_direction_stationary_below_epsilon():
    engine = TemporalEngine(camera_id="CAM-01")
    track = make_track(1, bbox=(0, 0, 10, 10))
    engine.update([track], [], zone_state(0.0, {1: None}, {}), timestamp=0.0)

    track.bbox = (0.5, 0.5, 10.5, 10.5)  # tiny jitter
    state2 = engine.update([track], [], zone_state(1.0, {1: None}, {}), timestamp=1.0)
    assert state2.entities[1].movement_direction == "stationary"


def test_zone_occupancy_change_and_entry_exit_counts_accumulate():
    engine = TemporalEngine(camera_id="CAM-01")

    zs1 = zone_state(0.0, {1: "Z1"}, {"Z1": 1}, events=[ZoneMembershipEvent(1, "Z1", "enter", 0.0)])
    state1 = engine.update([make_track(1, (0, 0, 10, 10))], [], zs1, timestamp=0.0)
    assert state1.zones["Z1"].occupancy_change == 1
    assert state1.zones["Z1"].entry_count == 1
    assert state1.zones["Z1"].exit_count == 0

    zs2 = zone_state(
        1.0, {2: "Z1"}, {"Z1": 2},
        events=[ZoneMembershipEvent(2, "Z1", "enter", 1.0)],
    )
    state2 = engine.update([make_track(2, (0, 0, 10, 10))], [], zs2, timestamp=1.0)
    assert state2.zones["Z1"].occupancy_change == 1  # 2 - 1
    assert state2.zones["Z1"].entry_count == 2

    zs3 = zone_state(2.0, {}, {"Z1": 0}, events=[ZoneMembershipEvent(2, "Z1", "exit", 2.0)])
    state3 = engine.update([], [], zs3, timestamp=2.0)
    assert state3.zones["Z1"].occupancy_change == -2
    assert state3.zones["Z1"].exit_count == 1


def test_dwell_distribution_summarizes_entities_in_zone():
    engine = TemporalEngine(camera_id="CAM-01")
    t1 = make_track(1, (0, 0, 10, 10))
    t2 = make_track(2, (0, 0, 10, 10))

    zs1 = zone_state(0.0, {1: "Z1", 2: "Z1"}, {"Z1": 2})
    engine.update([t1, t2], [], zs1, timestamp=0.0)

    zs2 = zone_state(10.0, {1: "Z1", 2: "Z1"}, {"Z1": 2})
    state2 = engine.update([t1, t2], [], zs2, timestamp=10.0)

    dist = state2.zones["Z1"].dwell_distribution
    assert dist["count"] == 2
    assert dist["mean"] == 10.0
    assert dist["max"] == 10.0


def test_congestion_state_thresholds():
    engine = TemporalEngine(camera_id="CAM-01", congestion_thresholds={"moderate_occupancy": 3, "high_occupancy": 6})

    low = engine.update([], [], zone_state(0.0, {}, {"Z1": 2}), timestamp=0.0)
    moderate = engine.update([], [], zone_state(1.0, {}, {"Z1": 3}), timestamp=1.0)
    high = engine.update([], [], zone_state(2.0, {}, {"Z1": 6}), timestamp=2.0)

    assert low.zones["Z1"].congestion_state == "low"
    assert moderate.zones["Z1"].congestion_state == "moderate"
    assert high.zones["Z1"].congestion_state == "high"


def test_hazard_presence_and_persistence_increments_then_resets():
    engine = TemporalEngine(camera_id="CAM-01", hazard_min_confidence=0.5)

    s1 = engine.update([], [make_detection("fire", 0.9)], zone_state(0.0, {}, {}), timestamp=0.0)
    assert s1.hazards["fire"].presence is True
    assert s1.hazards["fire"].persistence_frames == 1

    s2 = engine.update([], [make_detection("fire", 0.95)], zone_state(1.0, {}, {}), timestamp=1.0)
    assert s2.hazards["fire"].persistence_frames == 2
    assert s2.hazards["fire"].confidence == 0.95

    s3 = engine.update([], [], zone_state(2.0, {}, {}), timestamp=2.0)
    assert s3.hazards["fire"].presence is False
    assert s3.hazards["fire"].persistence_frames == 0
    assert s3.hazards["fire"].confidence == 0.0


def test_hazard_below_min_confidence_not_present():
    engine = TemporalEngine(camera_id="CAM-01", hazard_min_confidence=0.5)
    state = engine.update([], [make_detection("smoke", 0.2)], zone_state(0.0, {}, {}), timestamp=0.0)
    assert state.hazards == {}


def test_person_class_is_never_treated_as_a_hazard():
    engine = TemporalEngine(camera_id="CAM-01")
    state = engine.update([], [make_detection("person", 0.99)], zone_state(0.0, {}, {}), timestamp=0.0)
    assert state.hazards == {}


def test_exit_persistence_accumulates_while_occupied_and_resets_when_clear():
    engine = TemporalEngine(camera_id="CAM-01")

    s1 = engine.update([], [], zone_state(0.0, {}, {}, exit_occupancy={"EXIT-A": 1}), timestamp=0.0)
    assert s1.exits["EXIT-A"].state == "OCCUPIED"
    assert s1.exits["EXIT-A"].persistence_seconds == 0.0

    s2 = engine.update([], [], zone_state(4.0, {}, {}, exit_occupancy={"EXIT-A": 2}), timestamp=4.0)
    assert s2.exits["EXIT-A"].state == "OCCUPIED"
    assert s2.exits["EXIT-A"].persistence_seconds == 4.0

    s3 = engine.update([], [], zone_state(5.0, {}, {}, exit_occupancy={"EXIT-A": 0}), timestamp=5.0)
    assert s3.exits["EXIT-A"].state == "CLEAR"
    assert s3.exits["EXIT-A"].persistence_seconds == 0.0
    assert s3.exits["EXIT-A"].obstruction is False  # real classification is Phase 9


def test_from_thresholds_file_loads_real_config():
    engine = TemporalEngine.from_thresholds_file("configs/thresholds.json", camera_id="CAM-01")
    assert engine.congestion_thresholds == {"moderate_occupancy": 3, "high_occupancy": 6}
    assert engine.hazard_min_confidence == 0.5
