"""
Incident State — WORKFLOW.md Phase 11.

The single structured object the responder dashboard (Phase 13) and the
notification engine (Phase 12) both read. Everything here is assembled
from signals already produced by earlier phases (zone engine, temporal
engine, exit state machine, priority engine) — this module does not derive
any new spatial/temporal facts of its own, only synthesizes and narrates
them into one coherent snapshot plus a rolling timeline.

Answers the questions CLAUDE.md requires the dashboard to be able to
answer:
    WHO?              -> people
    WHAT?              -> hazards
    WHERE?             -> affected_zones
    WHAT CHANGED?      -> timeline
    IS IT GETTING WORSE? -> trend
    WHY DOES IT MATTER?  -> priority + contributors
    HOW CERTAIN ARE WE?  -> confidence + uncertainty
    WAS ANYONE NOTIFIED? -> notification
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The one detection class that represents a person. Kept as a named constant
# so the `people` filter below can't silently drift from the detector's
# validated_classes (configs/model_versions.json).
PERSON_CLASS_NAME = "person"


@dataclass
class IncidentPerson:
    track_id: int
    class_name: str
    current_zone: str | None
    confidence: float
    dwell_time: float
    movement_direction: str | None


@dataclass
class IncidentHazard:
    class_name: str
    presence: bool
    confidence: float
    persistence_frames: int


@dataclass
class IncidentExit:
    exit_id: str
    state: str
    occupancy: int
    persistence_seconds: float
    evidence_confidence: float | None


@dataclass
class IncidentZoneCongestion:
    zone_id: str
    occupancy: int
    congestion_state: str


@dataclass
class TimelineEvent:
    timestamp: float
    event_type: str  # zone_enter | zone_exit | exit_state_change | hazard_onset | hazard_cleared | priority_band_change
    description: str
    payload: dict = field(default_factory=dict)


@dataclass
class NotificationStatus:
    """Placeholder shape the notification engine (Phase 12) will populate
    via IncidentStateBuilder.set_notification(). Defaults to "not yet
    evaluated" — never fabricated as "sent"."""

    status: str = "not_sent"  # not_sent | pending | sent | failed | suppressed_cooldown | suppressed_not_persistent
    reason: str | None = None
    recipient_name: str | None = None
    sent_at: float | None = None


@dataclass
class IncidentState:
    timestamp: float
    camera_id: str
    priority: float
    band: str
    trend: str  # "stable" | "deteriorating" | "improving"
    affected_zones: list[str]
    people: list[IncidentPerson]
    hazards: list[IncidentHazard]
    exits: list[IncidentExit]
    congestion: dict[str, IncidentZoneCongestion]
    contributors: list[str]
    confidence: float
    uncertainty: bool
    notification: NotificationStatus
    timeline: list[TimelineEvent]
    # True while a real notification is latched active (see
    # NotificationEngine.is_alert_latched) — patched in by the pipeline
    # alongside `notification`, same pattern, same reason: this tick's
    # incident state needs the *current* dispatch decision, not last
    # tick's. Defaults False; `band`/`priority` themselves are never
    # latched and always report the honest instantaneous value.
    alert_active: bool = False


class IncidentStateBuilder:
    """Holds the cross-tick bookkeeping (previous priority/band/exit
    states/hazard presence, accumulated timeline, latest notification
    status) needed to assemble each tick's IncidentState."""

    def __init__(self, trend_deadband: float = 2.0, max_timeline_events: int = 500):
        self.trend_deadband = trend_deadband
        self.max_timeline_events = max_timeline_events

        self._previous_priority: float | None = None
        self._previous_band: str | None = None
        self._previous_exit_states: dict[str, str] = {}
        self._previous_hazard_presence: dict[str, bool] = {}
        self._timeline: list[TimelineEvent] = []
        self._last_notification = NotificationStatus()
        # track_id -> class_name, retained across ticks: a track that vacates
        # a zone by disappearing still emits an exit event on a tick where it
        # is no longer in `tracks`, and that event still needs a correct label.
        self._track_classes: dict[int, str] = {}

    def set_notification(self, notification: NotificationStatus) -> None:
        """Called by the notification engine (Phase 12) to attach its
        latest result; carried forward on subsequent ticks until updated
        again."""
        self._last_notification = notification

    def _append_timeline(self, events: list[TimelineEvent]) -> None:
        self._timeline.extend(events)
        if len(self._timeline) > self.max_timeline_events:
            self._timeline = self._timeline[-self.max_timeline_events :]

    def _trend(self, priority: float) -> str:
        if self._previous_priority is None:
            trend = "stable"
        else:
            delta = priority - self._previous_priority
            if delta > self.trend_deadband:
                trend = "deteriorating"
            elif delta < -self.trend_deadband:
                trend = "improving"
            else:
                trend = "stable"
        self._previous_priority = priority
        return trend

    def _zone_events(self, zone_state, timestamp: float, track_classes: dict[int, str]) -> list[TimelineEvent]:
        """ByteTrack tracks hazards as well as people, so a zone event's
        subject is not necessarily a person — label it by its actual class
        rather than assuming "Person", and carry class_name in the payload
        so consumers can filter without re-deriving it from the wording."""
        events = []
        for zevent in zone_state.events:
            class_name = track_classes.get(zevent.track_id, "entity")
            subject = f"{class_name.capitalize()} #{zevent.track_id}"
            events.append(
                TimelineEvent(
                    timestamp=timestamp,
                    event_type=f"zone_{zevent.event_type}",
                    description=f"{subject} {zevent.event_type}ed {zevent.zone_id}",
                    payload={"track_id": zevent.track_id, "zone_id": zevent.zone_id, "class_name": class_name},
                )
            )
        return events

    def _exit_transition_events(self, exit_states: dict, timestamp: float) -> list[TimelineEvent]:
        events = []
        for exit_id, result in exit_states.items():
            previous = self._previous_exit_states.get(exit_id)
            if previous is not None and previous != result.state.value:
                events.append(
                    TimelineEvent(
                        timestamp=timestamp,
                        event_type="exit_state_change",
                        description=f"{exit_id} changed {previous} -> {result.state.value}",
                        payload={"exit_id": exit_id, "from": previous, "to": result.state.value},
                    )
                )
            self._previous_exit_states[exit_id] = result.state.value
        return events

    def _hazard_transition_events(self, temporal_state, timestamp: float) -> list[TimelineEvent]:
        events = []
        for class_name, hazard in temporal_state.hazards.items():
            previous_presence = self._previous_hazard_presence.get(class_name, False)
            if hazard.presence and not previous_presence:
                events.append(
                    TimelineEvent(
                        timestamp=timestamp,
                        event_type="hazard_onset",
                        description=f"{class_name} detected",
                        payload={"class_name": class_name, "confidence": hazard.confidence},
                    )
                )
            elif not hazard.presence and previous_presence:
                events.append(
                    TimelineEvent(
                        timestamp=timestamp,
                        event_type="hazard_cleared",
                        description=f"{class_name} no longer detected",
                        payload={"class_name": class_name},
                    )
                )
            self._previous_hazard_presence[class_name] = hazard.presence
        return events

    def update(self, zone_state, temporal_state, exit_states: dict, priority_result, tracks: list, timestamp: float) -> IncidentState:
        """
        zone_state: vision.zones.engine.ZoneState (this tick)
        temporal_state: intelligence.temporal.engine.TemporalSceneState (this tick)
        exit_states: dict[str, intelligence.temporal.exit_state.ExitStateResult] (this tick)
        priority_result: intelligence.priority.engine.PriorityResult (this tick)
        tracks: this tick's vision.tracking.byte_tracker.Track list
        """
        for t in tracks:
            self._track_classes[t.track_id] = t.class_name

        new_events = self._zone_events(zone_state, timestamp, self._track_classes)
        new_events += self._exit_transition_events(exit_states, timestamp)
        new_events += self._hazard_transition_events(temporal_state, timestamp)

        trend = self._trend(priority_result.priority)
        if self._previous_band is not None and self._previous_band != priority_result.band:
            new_events.append(
                TimelineEvent(
                    timestamp=timestamp,
                    event_type="priority_band_change",
                    description=f"Priority band changed {self._previous_band} -> {priority_result.band}",
                    payload={"from": self._previous_band, "to": priority_result.band, "priority": priority_result.priority},
                )
            )
        self._previous_band = priority_result.band

        self._append_timeline(new_events)

        # ByteTrack is class-agnostic and tracks hazards (fire/smoke) as well
        # as people, so `tracks` can contain non-person entities. `people` is
        # the dashboard's "who is at risk" list and must only ever contain
        # actual people — hazards are surfaced separately via `hazards` below,
        # and remain fully available to the temporal/priority engines, which
        # read the raw detection stream rather than this list.
        people = [
            IncidentPerson(
                track_id=t.track_id,
                class_name=t.class_name,
                current_zone=zone_state.track_zone.get(t.track_id),
                confidence=t.confidence,
                dwell_time=temporal_state.entities[t.track_id].dwell_time if t.track_id in temporal_state.entities else 0.0,
                movement_direction=(
                    temporal_state.entities[t.track_id].movement_direction if t.track_id in temporal_state.entities else None
                ),
            )
            for t in tracks
            if t.class_name == PERSON_CLASS_NAME
        ]

        hazards = [
            IncidentHazard(
                class_name=h.class_name, presence=h.presence, confidence=h.confidence, persistence_frames=h.persistence_frames
            )
            for h in temporal_state.hazards.values()
            if h.presence
        ]

        exits = [
            IncidentExit(
                exit_id=exit_id,
                state=result.state.value,
                occupancy=result.occupancy,
                persistence_seconds=result.persistence_seconds,
                evidence_confidence=result.evidence_confidence,
            )
            for exit_id, result in exit_states.items()
        ]

        congestion = {
            zone_id: IncidentZoneCongestion(zone_id=zone_id, occupancy=zt.occupancy, congestion_state=zt.congestion_state)
            for zone_id, zt in temporal_state.zones.items()
        }

        affected_zones = [zone_id for zone_id, occupancy in zone_state.zone_occupancy.items() if occupancy > 0]

        return IncidentState(
            timestamp=timestamp,
            camera_id=zone_state.camera_id,
            priority=priority_result.priority,
            band=priority_result.band,
            trend=trend,
            affected_zones=affected_zones,
            people=people,
            hazards=hazards,
            exits=exits,
            congestion=congestion,
            contributors=priority_result.contributors,
            confidence=priority_result.confidence,
            uncertainty=priority_result.uncertainty,
            notification=self._last_notification,
            timeline=list(self._timeline),
        )
