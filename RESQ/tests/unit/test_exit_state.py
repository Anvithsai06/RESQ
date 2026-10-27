"""
Unit tests for the exit state machine (WORKFLOW.md Phase 9):
CLEAR -> OCCUPIED -> OBSTRUCTED, gated by persistence and evidence
confidence, with weak/missing evidence always reported as UNCERTAIN.
"""
from intelligence.temporal.engine import ExitTemporalState
from intelligence.temporal.exit_state import ExitState, ExitStateEngine
from vision.tracking.byte_tracker import Track


def make_track(track_id, confidence):
    return Track(
        track_id=track_id,
        class_name="person",
        bbox=(0, 0, 10, 10),
        confidence=confidence,
        first_seen=0.0,
        last_seen=0.0,
        trajectory=[],
        camera_id="CAM-01",
    )


def temporal_exit(exit_id, occupancy, persistence_seconds, obstruction=False, state="OCCUPIED"):
    return ExitTemporalState(
        exit_id=exit_id, occupancy=occupancy, persistence_seconds=persistence_seconds,
        obstruction=obstruction, state=state,
    )


def test_zero_occupancy_is_clear_with_no_evidence():
    engine = ExitStateEngine(default_persistence_seconds=5.0, evidence_min_confidence=0.5)
    temporal = {"EXIT-A": temporal_exit("EXIT-A", occupancy=0, persistence_seconds=0.0, state="CLEAR")}

    result = engine.update(temporal, tracks=[], track_exit={})["EXIT-A"]

    assert result.state == ExitState.CLEAR
    assert result.evidence_confidence is None


def test_occupied_below_persistence_threshold_with_good_evidence():
    engine = ExitStateEngine(default_persistence_seconds=5.0, evidence_min_confidence=0.5)
    temporal = {"EXIT-A": temporal_exit("EXIT-A", occupancy=1, persistence_seconds=2.0)}
    tracks = [make_track(1, confidence=0.9)]

    result = engine.update(temporal, tracks, track_exit={1: "EXIT-A"})["EXIT-A"]

    assert result.state == ExitState.OCCUPIED
    assert result.evidence_confidence == 0.9


def test_obstructed_once_persistence_threshold_reached_with_good_evidence():
    engine = ExitStateEngine(default_persistence_seconds=5.0, evidence_min_confidence=0.5)
    temporal = {"EXIT-A": temporal_exit("EXIT-A", occupancy=1, persistence_seconds=5.0)}
    tracks = [make_track(1, confidence=0.9)]

    result = engine.update(temporal, tracks, track_exit={1: "EXIT-A"})["EXIT-A"]

    assert result.state == ExitState.OBSTRUCTED


def test_weak_evidence_is_uncertain_even_past_persistence_threshold():
    engine = ExitStateEngine(default_persistence_seconds=5.0, evidence_min_confidence=0.5)
    temporal = {"EXIT-A": temporal_exit("EXIT-A", occupancy=1, persistence_seconds=10.0)}
    tracks = [make_track(1, confidence=0.2)]  # below evidence_min_confidence

    result = engine.update(temporal, tracks, track_exit={1: "EXIT-A"})["EXIT-A"]

    assert result.state == ExitState.UNCERTAIN


def test_missing_evidence_treated_as_uncertain():
    engine = ExitStateEngine(default_persistence_seconds=5.0, evidence_min_confidence=0.5)
    # occupancy > 0 per temporal state, but no matching track found (e.g.
    # stale/edge-case data) — evidence_confidence defaults to 0.0.
    temporal = {"EXIT-A": temporal_exit("EXIT-A", occupancy=1, persistence_seconds=1.0)}

    result = engine.update(temporal, tracks=[], track_exit={})["EXIT-A"]

    assert result.state == ExitState.UNCERTAIN
    assert result.evidence_confidence == 0.0


def test_weakest_of_multiple_tracks_determines_evidence_confidence():
    engine = ExitStateEngine(default_persistence_seconds=5.0, evidence_min_confidence=0.5)
    temporal = {"EXIT-A": temporal_exit("EXIT-A", occupancy=2, persistence_seconds=1.0)}
    tracks = [make_track(1, confidence=0.95), make_track(2, confidence=0.3)]

    result = engine.update(temporal, tracks, track_exit={1: "EXIT-A", 2: "EXIT-A"})["EXIT-A"]

    assert result.evidence_confidence == 0.3
    assert result.state == ExitState.UNCERTAIN


def test_per_exit_persistence_threshold_overrides_default():
    engine = ExitStateEngine(
        default_persistence_seconds=5.0,
        per_exit_persistence_seconds={"EXIT-FAST": 1.0},
        evidence_min_confidence=0.5,
    )
    temporal = {"EXIT-FAST": temporal_exit("EXIT-FAST", occupancy=1, persistence_seconds=1.5)}
    tracks = [make_track(1, confidence=0.9)]

    result = engine.update(temporal, tracks, track_exit={1: "EXIT-FAST"})["EXIT-FAST"]

    assert result.state == ExitState.OBSTRUCTED  # 1.5s >= this exit's 1.0s threshold, though < default 5.0s


def test_from_config_files_loads_real_building_and_threshold_config():
    engine = ExitStateEngine.from_config_files("configs/thresholds.json", "building/exits.json")

    assert engine.default_persistence_seconds == 5
    assert engine.evidence_min_confidence == 0.5
    assert engine.per_exit_persistence_seconds["EXIT-A"] == 5
    assert engine.per_exit_persistence_seconds["EXIT-B"] == 5
