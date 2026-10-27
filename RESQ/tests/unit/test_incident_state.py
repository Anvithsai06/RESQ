"""
Unit tests for Incident State assembly (WORKFLOW.md Phase 11): the bridge
object combining zone/temporal/exit/priority output into one snapshot plus
a rolling timeline.
"""
from intelligence.incident.state import IncidentStateBuilder, NotificationStatus
from intelligence.priority.engine import PriorityComponentScores, PriorityResult
from intelligence.temporal.engine import EntityTemporalState, HazardTemporalState, TemporalSceneState, ZoneTemporalState
from intelligence.temporal.exit_state import ExitState, ExitStateResult
from vision.tracking.byte_tracker import Track
from vision.zones.engine import ZoneMembershipEvent, ZoneState

EMPTY_COMPONENTS = PriorityComponentScores(hazard_exposure=0, people_in_danger_zones=0, congestion=0, exit_obstruction=0)


def make_zone_state(timestamp, zone_occupancy=None, track_zone=None, events=None, camera_id="CAM-01"):
    return ZoneState(
        timestamp=timestamp, camera_id=camera_id, track_zone=track_zone or {}, track_exit={},
        zone_occupancy=zone_occupancy or {}, exit_occupancy={}, danger_zone_occupancy=0, events=events or [],
    )


def make_temporal_state(timestamp, entities=None, zones=None, hazards=None):
    return TemporalSceneState(
        timestamp=timestamp, camera_id="CAM-01", entities=entities or {}, zones=zones or {},
        hazards=hazards or {}, exits={},
    )


def make_priority_result(timestamp, priority, band, contributors=None, confidence=1.0, uncertainty=False):
    return PriorityResult(
        timestamp=timestamp, camera_id="CAM-01", priority=priority, band=band, components=EMPTY_COMPONENTS,
        contributors=contributors or [], confidence=confidence, uncertainty=uncertainty,
    )


def make_track(track_id, confidence=0.9, class_name="person"):
    return Track(
        track_id=track_id, class_name=class_name, bbox=(0, 0, 10, 10), confidence=confidence,
        first_seen=0.0, last_seen=0.0, trajectory=[], camera_id="CAM-01",
    )


def test_basic_fields_pass_through_from_priority_result():
    builder = IncidentStateBuilder()
    priority_result = make_priority_result(0.0, priority=55.0, band="high", contributors=["hazard_exposure"], confidence=0.8, uncertainty=True)

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, priority_result, [], timestamp=0.0)

    assert state.priority == 55.0
    assert state.band == "high"
    assert state.contributors == ["hazard_exposure"]
    assert state.confidence == 0.8
    assert state.uncertainty is True
    assert state.camera_id == "CAM-01"


def test_affected_zones_only_includes_occupied_zones():
    builder = IncidentStateBuilder()
    zone_state = make_zone_state(0.0, zone_occupancy={"Z1": 2, "Z2": 0, "Z3": 1})

    state = builder.update(zone_state, make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)

    assert set(state.affected_zones) == {"Z1", "Z3"}


def test_people_list_pulls_dwell_and_movement_from_temporal_state():
    builder = IncidentStateBuilder()
    track = make_track(1, confidence=0.85)
    entities = {1: EntityTemporalState(track_id=1, class_name="person", first_seen=0.0, last_seen=0.0,
                                         current_zone="Z1", previous_zone=None, dwell_time=3.5, movement_direction="down")}
    zone_state = make_zone_state(0.0, track_zone={1: "Z1"})

    state = builder.update(zone_state, make_temporal_state(0.0, entities=entities), {}, make_priority_result(0.0, 0, "normal"), [track], timestamp=0.0)

    assert len(state.people) == 1
    person = state.people[0]
    assert person.track_id == 1
    assert person.current_zone == "Z1"
    assert person.confidence == 0.85
    assert person.dwell_time == 3.5
    assert person.movement_direction == "down"


def test_people_list_defaults_gracefully_when_missing_from_temporal_state():
    builder = IncidentStateBuilder()
    track = make_track(1)

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), [track], timestamp=0.0)

    assert state.people[0].dwell_time == 0.0
    assert state.people[0].movement_direction is None


def test_person_tracks_appear_in_state_people():
    """Regression: ByteTrack is class-agnostic and also tracks hazards, so
    `people` must filter to actual people — see the fire/smoke tests below."""
    builder = IncidentStateBuilder()
    tracks = [make_track(1, class_name="person"), make_track(2, class_name="person")]

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), tracks, timestamp=0.0)

    assert {p.track_id for p in state.people} == {1, 2}
    assert all(p.class_name == "person" for p in state.people)


def test_fire_tracks_do_not_appear_in_state_people():
    builder = IncidentStateBuilder()
    tracks = [make_track(1, class_name="person"), make_track(2, class_name="fire")]

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), tracks, timestamp=0.0)

    assert [p.track_id for p in state.people] == [1]
    assert "fire" not in {p.class_name for p in state.people}


def test_smoke_tracks_do_not_appear_in_state_people():
    builder = IncidentStateBuilder()
    tracks = [make_track(1, class_name="person"), make_track(3, class_name="smoke")]

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), tracks, timestamp=0.0)

    assert [p.track_id for p in state.people] == [1]
    assert "smoke" not in {p.class_name for p in state.people}


def test_hazard_only_scene_yields_empty_people_but_keeps_hazards():
    """Hazards must stay fully available to hazard/incident intelligence
    even when no people are present — filtering `people` must not remove
    fire/smoke from the pipeline."""
    builder = IncidentStateBuilder()
    tracks = [make_track(2, class_name="fire"), make_track(3, class_name="smoke")]
    hazards = {
        "fire": HazardTemporalState(class_name="fire", camera_id="CAM-01", presence=True, confidence=0.8, persistence_frames=4),
    }

    state = builder.update(
        make_zone_state(0.0), make_temporal_state(0.0, hazards=hazards), {},
        make_priority_result(0.0, 0, "normal"), tracks, timestamp=0.0,
    )

    assert state.people == []
    assert [h.class_name for h in state.hazards] == ["fire"]


def test_hazards_filtered_to_currently_present_only():
    builder = IncidentStateBuilder()
    hazards = {
        "fire": HazardTemporalState(class_name="fire", camera_id="CAM-01", presence=True, confidence=0.9, persistence_frames=3),
        "smoke": HazardTemporalState(class_name="smoke", camera_id="CAM-01", presence=False, confidence=0.0, persistence_frames=0),
    }

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0, hazards=hazards), {}, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)

    assert [h.class_name for h in state.hazards] == ["fire"]


def test_exits_list_includes_all_exit_states():
    builder = IncidentStateBuilder()
    exit_states = {
        "EXIT-A": ExitStateResult(exit_id="EXIT-A", state=ExitState.CLEAR, occupancy=0, persistence_seconds=0.0, evidence_confidence=None),
        "EXIT-B": ExitStateResult(exit_id="EXIT-B", state=ExitState.OBSTRUCTED, occupancy=2, persistence_seconds=6.0, evidence_confidence=0.9),
    }

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0), exit_states, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)

    assert {e.exit_id: e.state for e in state.exits} == {"EXIT-A": "CLEAR", "EXIT-B": "OBSTRUCTED"}


def test_congestion_reflects_temporal_zone_states():
    builder = IncidentStateBuilder()
    zones = {"Z1": ZoneTemporalState(zone_id="Z1", occupancy=6, occupancy_change=0, entry_count=0, exit_count=0,
                                       dwell_distribution={}, congestion_state="high")}

    state = builder.update(make_zone_state(0.0), make_temporal_state(0.0, zones=zones), {}, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)

    assert state.congestion["Z1"].congestion_state == "high"
    assert state.congestion["Z1"].occupancy == 6


def test_timeline_records_zone_enter_and_exit_events():
    builder = IncidentStateBuilder()
    events = [ZoneMembershipEvent(track_id=1, zone_id="Z1", event_type="enter", timestamp=0.0)]
    zone_state = make_zone_state(0.0, events=events)
    track = make_track(1, class_name="person")

    state = builder.update(zone_state, make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), [track], timestamp=0.0)

    assert len(state.timeline) == 1
    assert state.timeline[0].event_type == "zone_enter"
    assert state.timeline[0].payload == {"track_id": 1, "zone_id": "Z1", "class_name": "person"}
    assert state.timeline[0].description == "Person #1 entered Z1"


def test_timeline_zone_event_labelled_by_actual_class_not_assumed_person():
    """Regression: the timeline used to hardcode "Person #N" for every
    track, mislabelling hazard tracks that ByteTrack also follows."""
    builder = IncidentStateBuilder()
    events = [ZoneMembershipEvent(track_id=9, zone_id="Z1", event_type="enter", timestamp=0.0)]
    zone_state = make_zone_state(0.0, events=events)
    fire_track = make_track(9, class_name="fire")

    state = builder.update(zone_state, make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), [fire_track], timestamp=0.0)

    assert state.timeline[0].payload["class_name"] == "fire"
    assert state.timeline[0].description == "Fire #9 entered Z1"
    assert "Person" not in state.timeline[0].description


def test_timeline_zone_event_for_unknown_track_uses_neutral_label():
    """A track that vacated a zone by disappearing before this builder ever
    saw it must not be guessed at — it gets a neutral subject, not "Person"."""
    builder = IncidentStateBuilder()
    events = [ZoneMembershipEvent(track_id=99, zone_id="Z1", event_type="exit", timestamp=0.0)]
    zone_state = make_zone_state(0.0, events=events)

    state = builder.update(zone_state, make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)

    assert state.timeline[0].payload["class_name"] == "entity"
    assert "Person" not in state.timeline[0].description


def test_timeline_records_exit_state_change_only_on_transition():
    builder = IncidentStateBuilder()
    exit_states_1 = {"EXIT-A": ExitStateResult(exit_id="EXIT-A", state=ExitState.CLEAR, occupancy=0, persistence_seconds=0.0, evidence_confidence=None)}
    builder.update(make_zone_state(0.0), make_temporal_state(0.0), exit_states_1, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)

    exit_states_2 = {"EXIT-A": ExitStateResult(exit_id="EXIT-A", state=ExitState.OBSTRUCTED, occupancy=1, persistence_seconds=6.0, evidence_confidence=0.9)}
    state2 = builder.update(make_zone_state(1.0), make_temporal_state(1.0), exit_states_2, make_priority_result(1.0, 0, "normal"), [], timestamp=1.0)

    transitions = [e for e in state2.timeline if e.event_type == "exit_state_change"]
    assert len(transitions) == 1
    assert transitions[0].payload == {"exit_id": "EXIT-A", "from": "CLEAR", "to": "OBSTRUCTED"}


def test_timeline_records_hazard_onset_and_cleared():
    builder = IncidentStateBuilder()
    present = {"fire": HazardTemporalState(class_name="fire", camera_id="CAM-01", presence=True, confidence=0.9, persistence_frames=1)}
    state1 = builder.update(make_zone_state(0.0), make_temporal_state(0.0, hazards=present), {}, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)
    assert any(e.event_type == "hazard_onset" for e in state1.timeline)

    cleared = {"fire": HazardTemporalState(class_name="fire", camera_id="CAM-01", presence=False, confidence=0.0, persistence_frames=0)}
    state2 = builder.update(make_zone_state(1.0), make_temporal_state(1.0, hazards=cleared), {}, make_priority_result(1.0, 0, "normal"), [], timestamp=1.0)
    assert any(e.event_type == "hazard_cleared" for e in state2.timeline)


def test_timeline_records_priority_band_change_but_not_on_first_tick():
    builder = IncidentStateBuilder()
    state1 = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, make_priority_result(0.0, 30, "normal"), [], timestamp=0.0)
    assert not any(e.event_type == "priority_band_change" for e in state1.timeline)

    state2 = builder.update(make_zone_state(1.0), make_temporal_state(1.0), {}, make_priority_result(1.0, 85, "critical"), [], timestamp=1.0)
    band_events = [e for e in state2.timeline if e.event_type == "priority_band_change"]
    assert len(band_events) == 1
    assert band_events[0].payload == {"from": "normal", "to": "critical", "priority": 85}


def test_trend_stable_on_first_tick_and_reacts_to_priority_deltas():
    builder = IncidentStateBuilder(trend_deadband=2.0)

    s1 = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, make_priority_result(0.0, 30, "normal"), [], timestamp=0.0)
    assert s1.trend == "stable"

    s2 = builder.update(make_zone_state(1.0), make_temporal_state(1.0), {}, make_priority_result(1.0, 60, "high"), [], timestamp=1.0)
    assert s2.trend == "deteriorating"

    s3 = builder.update(make_zone_state(2.0), make_temporal_state(2.0), {}, make_priority_result(2.0, 20, "normal"), [], timestamp=2.0)
    assert s3.trend == "improving"

    s4 = builder.update(make_zone_state(3.0), make_temporal_state(3.0), {}, make_priority_result(3.0, 21, "normal"), [], timestamp=3.0)
    assert s4.trend == "stable"  # within deadband of previous (20 -> 21)


def test_notification_defaults_not_sent_and_carries_forward_after_set():
    builder = IncidentStateBuilder()

    state1 = builder.update(make_zone_state(0.0), make_temporal_state(0.0), {}, make_priority_result(0.0, 0, "normal"), [], timestamp=0.0)
    assert state1.notification == NotificationStatus(status="not_sent", reason=None, recipient_name=None, sent_at=None)

    builder.set_notification(NotificationStatus(status="sent", reason=None, recipient_name="City Fire Dept", sent_at=42.0))
    state2 = builder.update(make_zone_state(1.0), make_temporal_state(1.0), {}, make_priority_result(1.0, 0, "normal"), [], timestamp=1.0)
    assert state2.notification.status == "sent"
    assert state2.notification.recipient_name == "City Fire Dept"


def test_timeline_trims_to_max_events():
    builder = IncidentStateBuilder(max_timeline_events=2)

    for i in range(5):
        events = [ZoneMembershipEvent(track_id=1, zone_id=f"Z{i}", event_type="enter", timestamp=float(i))]
        state = builder.update(
            make_zone_state(float(i), events=events), make_temporal_state(float(i)), {},
            make_priority_result(float(i), 0, "normal"), [], timestamp=float(i),
        )

    assert len(state.timeline) == 2
    assert state.timeline[-1].payload["zone_id"] == "Z4"
