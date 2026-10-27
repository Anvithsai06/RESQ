"""
Temporal scene-state engine — WORKFLOW.md Phase 7.

"This is where RESQ starts becoming more than object detection." Maintains
rolling state across ticks for entities, zones, hazards, and exits, built
on top of a single tick's ZoneEngine output (vision/zones/engine.py).

Exit `state` here is deliberately shallow (CLEAR/OCCUPIED only) — turning
sustained occupancy into a full CLEAR → OCCUPIED → OBSTRUCTED/UNCERTAIN
state machine, gated by persistence and confidence, is WORKFLOW.md Phase 9.
This engine's job is only to hand Phase 9 the raw persistence signal
(`persistence_seconds`) it needs to make that call.

Movement direction is expressed in image-space (up/down/left/right, from
the camera's point of view), never as a real-world compass bearing or
distance — RESQ does not claim exact real-world geometry from monocular
video.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

BBox = tuple[float, float, float, float]
Point = tuple[float, float]

_DEFAULT_CONGESTION_THRESHOLDS = {"moderate_occupancy": 3, "high_occupancy": 6}

# Any detected class other than "person" is treated as a hazard candidate —
# matches the current building/model config (validated_classes: ["person"],
# experimental_classes: ["fire", "smoke"]) without hardcoding hazard names.
_NON_HAZARD_CLASSES = {"person"}

# Minimum image-space displacement (pixels) before movement_direction is
# reported rather than "stationary" — filters out detector/tracker jitter.
_MOVEMENT_EPSILON = 2.0


def _bbox_center(bbox: BBox) -> Point:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _movement_direction(prev_point: Point, current_point: Point) -> str:
    dx = current_point[0] - prev_point[0]
    dy = current_point[1] - prev_point[1]
    if math.hypot(dx, dy) < _MOVEMENT_EPSILON:
        return "stationary"

    vertical = "down" if dy > 0 else "up" if dy < 0 else None
    horizontal = "right" if dx > 0 else "left" if dx < 0 else None

    if vertical and horizontal:
        return f"{vertical}-{horizontal}"
    return vertical or horizontal or "stationary"


@dataclass
class EntityTemporalState:
    track_id: int
    class_name: str
    first_seen: float
    last_seen: float
    current_zone: str | None
    previous_zone: str | None
    dwell_time: float  # seconds spent continuously in current_zone (0.0 if not in a zone)
    movement_direction: str | None  # image-space direction; None until 2+ observations exist


@dataclass
class ZoneTemporalState:
    zone_id: str
    occupancy: int
    occupancy_change: int  # delta vs. previous tick
    entry_count: int  # cumulative since engine start
    exit_count: int  # cumulative since engine start
    dwell_distribution: dict  # {"count": int, "mean": float, "max": float}
    congestion_state: str  # "low" | "moderate" | "high"


@dataclass
class HazardTemporalState:
    class_name: str
    camera_id: str
    presence: bool  # detected (>= min confidence) this tick
    confidence: float  # this tick's confidence, 0.0 if not present
    persistence_frames: int  # consecutive ticks with presence == True


@dataclass
class ExitTemporalState:
    exit_id: str
    occupancy: int
    persistence_seconds: float  # how long occupancy has been continuously > 0
    obstruction: bool  # placeholder — real classification is Phase 9
    state: str  # "CLEAR" | "OCCUPIED" — full state machine is Phase 9


@dataclass
class TemporalSceneState:
    timestamp: float
    camera_id: str
    entities: dict[int, EntityTemporalState] = field(default_factory=dict)
    zones: dict[str, ZoneTemporalState] = field(default_factory=dict)
    hazards: dict[str, HazardTemporalState] = field(default_factory=dict)
    exits: dict[str, ExitTemporalState] = field(default_factory=dict)


class TemporalEngine:
    """One instance per camera — holds all rolling state across ticks."""

    def __init__(self, camera_id: str, congestion_thresholds: dict | None = None,
                 hazard_min_confidence: float = 0.5):
        self.camera_id = camera_id
        self.congestion_thresholds = congestion_thresholds or dict(_DEFAULT_CONGESTION_THRESHOLDS)
        self.hazard_min_confidence = hazard_min_confidence

        self._entity_first_seen: dict[int, float] = {}
        self._entity_zone_entry_time: dict[int, float] = {}
        self._entity_prev_zone: dict[int, str | None] = {}
        self._entity_prev_point: dict[int, Point] = {}

        self._zone_prev_occupancy: dict[str, int] = {}
        self._zone_entry_count: dict[str, int] = {}
        self._zone_exit_count: dict[str, int] = {}

        self._hazard_streak: dict[str, int] = {}

        self._exit_occupied_since: dict[str, float | None] = {}

    @classmethod
    def from_thresholds_file(cls, path: str | Path, camera_id: str) -> "TemporalEngine":
        with open(path) as f:
            config = json.load(f)
        return cls(
            camera_id=camera_id,
            congestion_thresholds=config.get("congestion", dict(_DEFAULT_CONGESTION_THRESHOLDS)),
            hazard_min_confidence=config.get("hazard_detection_min_confidence", 0.5),
        )

    def _congestion_state(self, occupancy: int) -> str:
        if occupancy >= self.congestion_thresholds["high_occupancy"]:
            return "high"
        if occupancy >= self.congestion_thresholds["moderate_occupancy"]:
            return "moderate"
        return "low"

    def _update_entities(self, tracks: list, zone_state, timestamp: float) -> dict[int, EntityTemporalState]:
        entities: dict[int, EntityTemporalState] = {}
        for track in tracks:
            track_id = track.track_id
            current_zone = zone_state.track_zone.get(track_id)
            previous_zone = self._entity_prev_zone.get(track_id)

            first_seen = self._entity_first_seen.setdefault(track_id, track.first_seen)

            if current_zone != previous_zone:
                self._entity_zone_entry_time[track_id] = timestamp
            zone_entry_time = self._entity_zone_entry_time.get(track_id, timestamp)
            dwell_time = (timestamp - zone_entry_time) if current_zone is not None else 0.0

            current_point = _bbox_center(track.bbox)
            prev_point = self._entity_prev_point.get(track_id)
            movement_direction = _movement_direction(prev_point, current_point) if prev_point else None

            entities[track_id] = EntityTemporalState(
                track_id=track_id,
                class_name=track.class_name,
                first_seen=first_seen,
                last_seen=track.last_seen,
                current_zone=current_zone,
                previous_zone=previous_zone,
                dwell_time=dwell_time,
                movement_direction=movement_direction,
            )

            self._entity_prev_zone[track_id] = current_zone
            self._entity_prev_point[track_id] = current_point

        # Drop bookkeeping for tracks no longer present so memory doesn't
        # grow unbounded over a long-running demo.
        active_ids = {t.track_id for t in tracks}
        for stale_id in set(self._entity_prev_zone) - active_ids:
            self._entity_first_seen.pop(stale_id, None)
            self._entity_zone_entry_time.pop(stale_id, None)
            self._entity_prev_zone.pop(stale_id, None)
            self._entity_prev_point.pop(stale_id, None)

        return entities

    def _update_zones(self, zone_state, entities: dict[int, EntityTemporalState]) -> dict[str, ZoneTemporalState]:
        zones: dict[str, ZoneTemporalState] = {}
        for zone_id, occupancy in zone_state.zone_occupancy.items():
            previous_occupancy = self._zone_prev_occupancy.get(zone_id, 0)
            occupancy_change = occupancy - previous_occupancy
            self._zone_prev_occupancy[zone_id] = occupancy

            self._zone_entry_count.setdefault(zone_id, 0)
            self._zone_exit_count.setdefault(zone_id, 0)

            dwell_times = [e.dwell_time for e in entities.values() if e.current_zone == zone_id]
            dwell_distribution = {
                "count": len(dwell_times),
                "mean": (sum(dwell_times) / len(dwell_times)) if dwell_times else 0.0,
                "max": max(dwell_times) if dwell_times else 0.0,
            }

            zones[zone_id] = ZoneTemporalState(
                zone_id=zone_id,
                occupancy=occupancy,
                occupancy_change=occupancy_change,
                entry_count=self._zone_entry_count[zone_id],
                exit_count=self._zone_exit_count[zone_id],
                dwell_distribution=dwell_distribution,
                congestion_state=self._congestion_state(occupancy),
            )

        for event in zone_state.events:
            if event.event_type == "enter":
                self._zone_entry_count[event.zone_id] = self._zone_entry_count.get(event.zone_id, 0) + 1
                if event.zone_id in zones:
                    zones[event.zone_id].entry_count = self._zone_entry_count[event.zone_id]
            elif event.event_type == "exit":
                self._zone_exit_count[event.zone_id] = self._zone_exit_count.get(event.zone_id, 0) + 1
                if event.zone_id in zones:
                    zones[event.zone_id].exit_count = self._zone_exit_count[event.zone_id]

        return zones

    def _update_hazards(self, detections: list) -> dict[str, HazardTemporalState]:
        present_this_tick: dict[str, float] = {}
        for det in detections:
            if det.class_name in _NON_HAZARD_CLASSES:
                continue
            if det.confidence < self.hazard_min_confidence:
                continue
            present_this_tick[det.class_name] = max(present_this_tick.get(det.class_name, 0.0), det.confidence)

        hazards: dict[str, HazardTemporalState] = {}
        seen_classes = set(present_this_tick) | {c for c in self._hazard_streak}
        for class_name in seen_classes:
            if class_name in present_this_tick:
                self._hazard_streak[class_name] = self._hazard_streak.get(class_name, 0) + 1
                hazards[class_name] = HazardTemporalState(
                    class_name=class_name,
                    camera_id=self.camera_id,
                    presence=True,
                    confidence=present_this_tick[class_name],
                    persistence_frames=self._hazard_streak[class_name],
                )
            else:
                self._hazard_streak[class_name] = 0
                hazards[class_name] = HazardTemporalState(
                    class_name=class_name,
                    camera_id=self.camera_id,
                    presence=False,
                    confidence=0.0,
                    persistence_frames=0,
                )
        return hazards

    def _update_exits(self, zone_state, timestamp: float) -> dict[str, ExitTemporalState]:
        exits: dict[str, ExitTemporalState] = {}
        for exit_id, occupancy in zone_state.exit_occupancy.items():
            if occupancy > 0:
                if self._exit_occupied_since.get(exit_id) is None:
                    self._exit_occupied_since[exit_id] = timestamp
                persistence_seconds = timestamp - self._exit_occupied_since[exit_id]
                state = "OCCUPIED"
            else:
                self._exit_occupied_since[exit_id] = None
                persistence_seconds = 0.0
                state = "CLEAR"

            exits[exit_id] = ExitTemporalState(
                exit_id=exit_id,
                occupancy=occupancy,
                persistence_seconds=persistence_seconds,
                obstruction=False,
                state=state,
            )
        return exits

    def update(self, tracks: list, detections: list, zone_state, timestamp: float) -> TemporalSceneState:
        """`tracks` are this tick's vision.tracking.byte_tracker.Track list,
        `detections` this tick's vision.detection.detector.Detection list,
        `zone_state` this tick's vision.zones.engine.ZoneState."""
        entities = self._update_entities(tracks, zone_state, timestamp)
        zones = self._update_zones(zone_state, entities)
        hazards = self._update_hazards(detections)
        exits = self._update_exits(zone_state, timestamp)

        return TemporalSceneState(
            timestamp=timestamp,
            camera_id=self.camera_id,
            entities=entities,
            zones=zones,
            hazards=hazards,
            exits=exits,
        )
