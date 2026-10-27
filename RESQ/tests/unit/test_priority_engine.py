"""
Unit tests for the priority engine (WORKFLOW.md Phase 10): weighted 0-100
component scoring, contributors, confidence, and uncertainty.
"""
import pytest

from intelligence.priority.engine import PriorityEngine
from intelligence.temporal.engine import HazardTemporalState, ZoneTemporalState
from intelligence.temporal.exit_state import ExitState, ExitStateResult
from vision.tracking.byte_tracker import Track
from vision.zones.engine import ZoneState

WEIGHTS = {"hazard_exposure": 0.40, "people_in_danger_zones": 0.25, "congestion": 0.20, "exit_obstruction": 0.15}
BANDS = {"moderate": 40, "high": 60, "critical": 80}
REAL_BANDS = {"moderate": 30, "high": 45, "critical": 60}  # configs/thresholds.json's actual, rebalanced values
EXIT_SCORES = {"CLEAR": 0, "OCCUPIED": 20, "UNCERTAIN": 35, "OBSTRUCTED": 100}


def make_engine(validated_hazard_classes=frozenset({"fire", "smoke"})):
    return PriorityEngine(
        weights=WEIGHTS,
        bands=BANDS,
        danger_zone_occupancy_saturation=5,
        congestion_high_occupancy=6,
        hazard_persistence_frames=10,
        exit_obstruction_component_scores=EXIT_SCORES,
        uncertainty_min_confidence=0.6,
        validated_hazard_classes=set(validated_hazard_classes),
    )


def make_zone_state(danger_zone_occupancy=0, camera_id="CAM-01"):
    return ZoneState(
        timestamp=0.0, camera_id=camera_id, track_zone={}, track_exit={},
        zone_occupancy={}, exit_occupancy={}, danger_zone_occupancy=danger_zone_occupancy, events=[],
    )


class FakeTemporalState:
    def __init__(self, zones=None, hazards=None):
        self.zones = zones or {}
        self.hazards = hazards or {}


def make_zone_temporal(zone_id, occupancy):
    return ZoneTemporalState(
        zone_id=zone_id, occupancy=occupancy, occupancy_change=0, entry_count=0, exit_count=0,
        dwell_distribution={"count": 0, "mean": 0.0, "max": 0.0}, congestion_state="low",
    )


def make_hazard(class_name, confidence, persistence_frames, presence=True):
    return HazardTemporalState(
        class_name=class_name, camera_id="CAM-01", presence=presence,
        confidence=confidence, persistence_frames=persistence_frames,
    )


def make_exit_result(exit_id, state, evidence_confidence):
    return ExitStateResult(
        exit_id=exit_id, state=state, occupancy=1 if state != ExitState.CLEAR else 0,
        persistence_seconds=0.0, evidence_confidence=evidence_confidence,
    )


def make_track(track_id, confidence):
    return Track(
        track_id=track_id, class_name="person", bbox=(0, 0, 10, 10), confidence=confidence,
        first_seen=0.0, last_seen=0.0, trajectory=[], camera_id="CAM-01",
    )


def test_all_clear_scene_has_zero_priority_and_full_confidence():
    engine = make_engine()
    result = engine.update(make_zone_state(), FakeTemporalState(), {}, [], timestamp=0.0)

    assert result.priority == 0
    assert result.band == "normal"
    assert result.contributors == []
    assert result.confidence == 1.0
    assert result.uncertainty is False


def test_hazard_exposure_alone_drives_priority():
    engine = make_engine()
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.9, persistence_frames=10)})

    result = engine.update(make_zone_state(), temporal, {}, [], timestamp=0.0)

    assert result.components.hazard_exposure == 90.0
    assert result.priority == 0.40 * 90.0
    assert result.contributors == ["hazard_exposure"]


def test_hazard_score_scales_with_persistence_ratio():
    engine = make_engine()
    # Only 5 of the required 10 persistence frames -> half-strength score.
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=1.0, persistence_frames=5)})

    result = engine.update(make_zone_state(), temporal, {}, [], timestamp=0.0)

    assert result.components.hazard_exposure == 50.0


def test_people_in_danger_zones_saturates_at_configured_count():
    engine = make_engine()

    result = engine.update(make_zone_state(danger_zone_occupancy=5), FakeTemporalState(), {}, [], timestamp=0.0)

    assert result.components.people_in_danger_zones == 100.0
    assert result.priority == 0.25 * 100.0
    assert result.contributors == ["people_in_danger_zones"]


def test_congestion_uses_max_zone_occupancy_saturated_at_high_threshold():
    engine = make_engine()
    temporal = FakeTemporalState(zones={"Z1": make_zone_temporal("Z1", occupancy=3), "Z2": make_zone_temporal("Z2", occupancy=6)})

    result = engine.update(make_zone_state(), temporal, {}, [], timestamp=0.0)

    assert result.components.congestion == 100.0  # driven by Z2's occupancy of 6
    assert result.contributors == ["congestion"]


def test_exit_obstruction_uses_worst_exit():
    engine = make_engine()
    exit_states = {
        "EXIT-A": make_exit_result("EXIT-A", ExitState.CLEAR, None),
        "EXIT-B": make_exit_result("EXIT-B", ExitState.OBSTRUCTED, 0.9),
    }

    result = engine.update(make_zone_state(), FakeTemporalState(), exit_states, [], timestamp=0.0)

    assert result.components.exit_obstruction == 100.0
    assert result.priority == 0.15 * 100.0
    assert result.contributors == ["exit_obstruction"]


def test_all_components_maxed_gives_priority_100_and_critical_band():
    engine = make_engine()
    temporal = FakeTemporalState(
        zones={"Z1": make_zone_temporal("Z1", occupancy=6)},
        hazards={"fire": make_hazard("fire", confidence=1.0, persistence_frames=10)},
    )
    exit_states = {"EXIT-A": make_exit_result("EXIT-A", ExitState.OBSTRUCTED, 1.0)}

    result = engine.update(make_zone_state(danger_zone_occupancy=5), temporal, exit_states, [], timestamp=0.0)

    assert result.priority == 100.0
    assert result.band == "critical"
    assert set(result.contributors) == {"hazard_exposure", "people_in_danger_zones", "congestion", "exit_obstruction"}


def test_contributors_sorted_by_weighted_contribution_not_raw_score():
    engine = make_engine()
    # Raw scores: hazard=20 (weighted 8), danger=40 (weighted 10), exit=100 (weighted 15).
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.2, persistence_frames=10)})
    exit_states = {"EXIT-A": make_exit_result("EXIT-A", ExitState.OBSTRUCTED, 1.0)}

    result = engine.update(make_zone_state(danger_zone_occupancy=2), temporal, exit_states, [], timestamp=0.0)

    assert result.contributors == ["exit_obstruction", "people_in_danger_zones", "hazard_exposure"]


def test_band_boundaries_are_inclusive_lower_bound():
    engine = make_engine()
    # people_in_danger_zones alone at occupancy=2 -> score 40 -> weighted 0.25*40=10 (too low to hit bands directly);
    # use exit_obstruction OCCUPIED(20) + hazard tuned to land exactly on 40/60/80.
    exit_states = {"EXIT-A": make_exit_result("EXIT-A", ExitState.OCCUPIED, 1.0)}  # weighted 0.15*20=3
    # Solve for hazard confidence c (full persistence) s.t. 0.40*100c + 3 == 40 -> c == 0.925
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.925, persistence_frames=10)})

    result = engine.update(make_zone_state(), temporal, exit_states, [], timestamp=0.0)

    assert result.priority == 40.0
    assert result.band == "moderate"


def test_confidence_averages_all_contributing_evidence():
    engine = make_engine()
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.8, persistence_frames=10)})
    exit_states = {"EXIT-A": make_exit_result("EXIT-A", ExitState.OCCUPIED, 0.6)}
    tracks = [make_track(1, confidence=0.7), make_track(2, confidence=0.9)]

    result = engine.update(make_zone_state(), temporal, exit_states, tracks, timestamp=0.0)

    # mean of [0.8, 0.6, 0.7, 0.9]
    assert result.confidence == (0.8 + 0.6 + 0.7 + 0.9) / 4


def test_uncertainty_true_when_confidence_below_threshold():
    engine = make_engine()
    tracks = [make_track(1, confidence=0.3)]  # drags average confidence below 0.6

    result = engine.update(make_zone_state(), FakeTemporalState(), {}, tracks, timestamp=0.0)

    assert result.confidence < 0.6
    assert result.uncertainty is True


def test_uncertainty_true_when_any_exit_is_uncertain_even_with_high_confidence():
    engine = make_engine()
    exit_states = {"EXIT-A": make_exit_result("EXIT-A", ExitState.UNCERTAIN, 0.9)}

    result = engine.update(make_zone_state(), FakeTemporalState(), exit_states, [], timestamp=0.0)

    assert result.confidence >= 0.6
    assert result.uncertainty is True


def test_uncertainty_true_when_unvalidated_hazard_class_contributes():
    engine = make_engine(validated_hazard_classes=set())  # "fire" is not validated in this engine instance
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.9, persistence_frames=10)})

    result = engine.update(make_zone_state(), temporal, {}, [], timestamp=0.0)

    assert result.confidence >= 0.6
    assert result.uncertainty is True


def test_uncertainty_false_when_validated_hazard_and_good_confidence():
    engine = make_engine(validated_hazard_classes={"fire"})
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.9, persistence_frames=10)})

    result = engine.update(make_zone_state(), temporal, {}, [], timestamp=0.0)

    assert result.uncertainty is False


def test_from_config_files_loads_real_config():
    engine = PriorityEngine.from_config_files("configs/thresholds.json", "configs/model_versions.json")

    assert engine.weights == WEIGHTS
    assert engine.bands == REAL_BANDS
    assert engine.danger_zone_occupancy_saturation == 5
    assert engine.congestion_high_occupancy == 6
    assert engine.hazard_persistence_frames == 10
    assert engine.exit_obstruction_component_scores == EXIT_SCORES
    assert engine.uncertainty_min_confidence == 0.6
    # hazard_risk weights load regardless of zones_path; only the per-zone
    # flammability *values* need zones_path (see the test below) — without
    # it, every zone falls back to default_flammability.
    assert engine.zone_flammability == {}
    assert engine.default_flammability == 0.3


def test_from_config_files_loads_flammability_when_zones_path_given():
    engine = PriorityEngine.from_config_files(
        "configs/thresholds.json", "configs/model_versions.json", "building/zones.json"
    )

    assert engine.zone_flammability["DANGER-A"] == 0.75
    assert engine.zone_flammability["DANGER-B"] == 0.85
    assert engine.zone_flammability["OBSTRUCTION-1"] == 0.6
    assert engine.zone_flammability["SAFE-OBS"] == 0.15
    assert engine.default_flammability == 0.3
    assert engine.flammability_weight == 0.35
    assert engine.occupied_zone_bonus == 0.15
    assert engine.growth_window_seconds == 5.0
    assert engine.growth_rate_scale == 1.0
    assert engine.growth_max_boost == 0.25
    assert engine.validated_hazard_classes == {"person"}


# ---------------------------------------------------------------------------
# Task 1.2/1.3: zone-flammability and growth-rate hazard risk factors.
# ---------------------------------------------------------------------------

def make_risk_engine(**overrides):
    kwargs = dict(
        weights=WEIGHTS, bands=BANDS, danger_zone_occupancy_saturation=5, congestion_high_occupancy=6,
        hazard_persistence_frames=10, exit_obstruction_component_scores=EXIT_SCORES,
        uncertainty_min_confidence=0.6, validated_hazard_classes={"fire", "smoke"},
    )
    kwargs.update(overrides)
    return PriorityEngine(**kwargs)


def make_hazard_track(track_id, class_name, bbox, confidence=0.9):
    return Track(
        track_id=track_id, class_name=class_name, bbox=bbox, confidence=confidence,
        first_seen=0.0, last_seen=0.0, trajectory=[], camera_id="CAM-01",
    )


def zone_state_with_tracks(track_zone=None, zone_occupancy=None):
    return ZoneState(
        timestamp=0.0, camera_id="CAM-01", track_zone=track_zone or {}, track_exit={},
        zone_occupancy=zone_occupancy or {}, exit_occupancy={}, danger_zone_occupancy=0, events=[],
    )


def test_flammability_boosts_score_for_hazard_in_flammable_zone():
    baseline_engine = make_risk_engine(flammability_weight=0.5, zone_flammability={})
    flammable_engine = make_risk_engine(flammability_weight=0.5, zone_flammability={"Z1": 1.0})

    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.8, persistence_frames=10)})
    track = make_hazard_track(1, "fire", (0, 0, 10, 10))
    zone_state = zone_state_with_tracks(track_zone={1: "Z1"})

    baseline = baseline_engine.update(zone_state, temporal, {}, [track], timestamp=0.0)
    flammable = flammable_engine.update(zone_state, temporal, {}, [track], timestamp=0.0)

    # baseline has no configured flammability for Z1, falls back to
    # default_flammability (0.3 default); the flammable engine explicitly
    # rates Z1 as maximally flammable, so its score must be strictly higher.
    assert flammable.components.hazard_exposure > baseline.components.hazard_exposure


def test_occupied_zone_bonus_boosts_score_when_zone_has_people():
    engine = make_risk_engine(flammability_weight=0.0, occupied_zone_bonus=0.4, zone_flammability={})
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.7, persistence_frames=10)})
    fire_track = make_hazard_track(1, "fire", (0, 0, 10, 10))
    person_track = make_hazard_track(2, "person", (20, 20, 30, 30))

    empty_zone = engine.update(zone_state_with_tracks(track_zone={1: "Z1"}), temporal, {}, [fire_track], timestamp=0.0)
    occupied_zone = engine.update(
        zone_state_with_tracks(track_zone={1: "Z1", 2: "Z1"}, zone_occupancy={"Z1": 1}),
        temporal, {}, [fire_track, person_track], timestamp=1.0,
    )

    assert occupied_zone.components.hazard_exposure > empty_zone.components.hazard_exposure


def test_hazard_score_never_exceeds_100_with_all_boosts_maxed():
    engine = make_risk_engine(
        flammability_weight=1.0, occupied_zone_bonus=1.0, zone_flammability={"Z1": 1.0},
        growth_window_seconds=10, growth_rate_scale=100, growth_max_boost=2.0,
    )
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=1.0, persistence_frames=10)})
    small = make_hazard_track(1, "fire", (0, 0, 10, 10))
    large = make_hazard_track(1, "fire", (0, 0, 200, 200))  # huge area growth for the same track_id
    zone_state = zone_state_with_tracks(track_zone={1: "Z1"}, zone_occupancy={"Z1": 3})

    engine.update(zone_state, temporal, {}, [small], timestamp=0.0)
    result = engine.update(zone_state, temporal, {}, [large], timestamp=1.0)

    assert result.components.hazard_exposure == 100.0


def test_growth_multiplier_boosts_score_for_visibly_growing_hazard():
    growing_engine = make_risk_engine(growth_window_seconds=10, growth_rate_scale=1.0, growth_max_boost=0.5)
    stable_engine = make_risk_engine(growth_window_seconds=10, growth_rate_scale=1.0, growth_max_boost=0.5)
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.6, persistence_frames=10)})
    zone_state = zone_state_with_tracks()

    # Growing: bbox area roughly doubles between ticks.
    growing_engine.update(zone_state, temporal, {}, [make_hazard_track(1, "fire", (0, 0, 20, 20))], timestamp=0.0)
    growing = growing_engine.update(zone_state, temporal, {}, [make_hazard_track(1, "fire", (0, 0, 40, 40))], timestamp=2.0)

    # Stable: identical bbox area both ticks.
    stable_engine.update(zone_state, temporal, {}, [make_hazard_track(1, "fire", (0, 0, 20, 20))], timestamp=0.0)
    stable = stable_engine.update(zone_state, temporal, {}, [make_hazard_track(1, "fire", (0, 0, 20, 20))], timestamp=2.0)

    assert growing.components.hazard_exposure > stable.components.hazard_exposure


def test_growth_multiplier_does_not_penalize_shrinking_hazard():
    engine = make_risk_engine(growth_window_seconds=10, growth_rate_scale=1.0, growth_max_boost=0.5)
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.6, persistence_frames=10)})
    zone_state = zone_state_with_tracks()

    engine.update(zone_state, temporal, {}, [make_hazard_track(1, "fire", (0, 0, 40, 40))], timestamp=0.0)
    shrinking = engine.update(zone_state, temporal, {}, [make_hazard_track(1, "fire", (0, 0, 20, 20))], timestamp=2.0)

    # confidence x persistence-ratio only (persistence_frames=10 -> ratio 1.0)
    # — no growth boost (it shrank) and no penalty either.
    base_score = 0.6 * min(1.0, 10 / 10) * 100.0
    assert shrinking.components.hazard_exposure == pytest.approx(base_score)


def test_growth_multiplier_needs_two_samples_within_window():
    """A single observation can't establish a trend — no boost on the first
    tick a hazard is ever seen, regardless of how large it already is."""
    engine = make_risk_engine(growth_window_seconds=10, growth_rate_scale=1.0, growth_max_boost=0.5)
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.6, persistence_frames=10)})

    result = engine.update(
        zone_state_with_tracks(), temporal, {}, [make_hazard_track(1, "fire", (0, 0, 200, 200))], timestamp=0.0
    )

    base_score = 0.6 * min(1.0, 10 / 10) * 100.0
    assert result.components.hazard_exposure == pytest.approx(base_score)


def test_zero_weight_risk_factors_reproduce_original_score_exactly():
    """Regression: with the new risk factors at their old-behavior defaults
    (all zero/off), hazard scoring is byte-for-byte identical to before
    Task 1 — existing deployments/tests aren't silently changed."""
    engine = make_risk_engine()  # flammability_weight/occupied_zone_bonus/growth_max_boost all default to 0.0
    temporal = FakeTemporalState(hazards={"fire": make_hazard("fire", confidence=0.8, persistence_frames=5)})

    result = engine.update(zone_state_with_tracks(), temporal, {}, [], timestamp=0.0)

    assert result.components.hazard_exposure == pytest.approx(0.8 * (5 / 10) * 100.0)
