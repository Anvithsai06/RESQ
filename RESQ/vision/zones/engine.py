"""
Zone engine — WORKFLOW.md Phase 6.

Converts tracked people into spatial state using OpenCV's polygon-membership
test (README: "OpenCV polygon engine"):

    Track → Point/bbox reference → Polygon membership → Zone

Only zones/exits defined in building/zones.json and building/exits.json are
ever evaluated — nothing is inferred. Exits are further filtered to
`trusted: true`, per WORKFLOW.md Phase 9's rule that an unconfigured door is
never treated as an emergency exit; that filter is applied here too since
exit occupancy is already computed at this stage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

Point = tuple[float, float]
Polygon = list[tuple[float, float]]
BBox = tuple[float, float, float, float]


@dataclass
class Zone:
    id: str
    type: str  # danger | obstruction | safe_observation
    label: str
    polygon: Polygon

    @classmethod
    def from_file(cls, path: str | Path) -> list["Zone"]:
        with open(path) as f:
            config = json.load(f)
        return [
            cls(id=z["id"], type=z["type"], label=z.get("label", z["id"]), polygon=[tuple(p) for p in z["polygon"]])
            for z in config["zones"]
        ]


@dataclass
class Exit:
    id: str
    label: str
    polygon: Polygon
    trusted: bool

    @classmethod
    def from_file(cls, path: str | Path) -> list["Exit"]:
        with open(path) as f:
            config = json.load(f)
        return [
            cls(
                id=e["id"],
                label=e.get("label", e["id"]),
                polygon=[tuple(p) for p in e["polygon"]],
                trusted=e.get("trusted", False),
            )
            for e in config["exits"]
        ]


@dataclass
class ZoneMembershipEvent:
    track_id: int
    zone_id: str
    event_type: str  # "enter" | "exit"
    timestamp: float


@dataclass
class ZoneState:
    timestamp: float
    camera_id: str
    track_zone: dict[int, str | None]
    track_exit: dict[int, str | None]
    zone_occupancy: dict[str, int]
    exit_occupancy: dict[str, int]
    danger_zone_occupancy: int
    events: list[ZoneMembershipEvent] = field(default_factory=list)


def reference_point(bbox: BBox) -> Point:
    """Bottom-center of the bbox — approximates where a person's feet touch
    the ground, which is what should be tested against floor-plane zone
    polygons (the bbox center would float mid-body, above the floor)."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def _point_in_polygon(point: Point, polygon: Polygon) -> bool:
    contour = np.array(polygon, dtype=np.float32).reshape((-1, 1, 2))
    return cv2.pointPolygonTest(contour, point, False) >= 0


class ZoneEngine:
    """One instance per camera — holds zone/exit polygons and per-track
    membership history so it can emit enter/exit events across ticks."""

    def __init__(self, zones: list[Zone], exits: list[Exit], camera_id: str):
        self.zones = zones
        self.exits = [e for e in exits if e.trusted]
        self.camera_id = camera_id
        self._prev_track_zone: dict[int, str | None] = {}

    @classmethod
    def from_files(cls, zones_path: str | Path, exits_path: str | Path, camera_id: str) -> "ZoneEngine":
        return cls(zones=Zone.from_file(zones_path), exits=Exit.from_file(exits_path), camera_id=camera_id)

    def _find_zone(self, point: Point) -> str | None:
        for zone in self.zones:
            if _point_in_polygon(point, zone.polygon):
                return zone.id
        return None

    def _find_exit(self, point: Point) -> str | None:
        for exit_ in self.exits:
            if _point_in_polygon(point, exit_.polygon):
                return exit_.id
        return None

    def update(self, tracks: list, timestamp: float) -> ZoneState:
        """`tracks` is a list of vision.tracking.byte_tracker.Track for the
        current frame. Each track's `current_zone` is updated in place."""
        track_zone: dict[int, str | None] = {}
        track_exit: dict[int, str | None] = {}
        events: list[ZoneMembershipEvent] = []
        current_track_ids: set[int] = set()

        for track in tracks:
            current_track_ids.add(track.track_id)
            point = reference_point(track.bbox)
            zone_id = self._find_zone(point)
            exit_id = self._find_exit(point)

            track_zone[track.track_id] = zone_id
            track_exit[track.track_id] = exit_id
            track.current_zone = zone_id

            prev_zone = self._prev_track_zone.get(track.track_id)
            if zone_id != prev_zone:
                if prev_zone is not None:
                    events.append(ZoneMembershipEvent(track.track_id, prev_zone, "exit", timestamp))
                if zone_id is not None:
                    events.append(ZoneMembershipEvent(track.track_id, zone_id, "enter", timestamp))

        # Tracks no longer present this frame (lost/removed) also vacate
        # whatever zone they last occupied.
        for old_track_id, old_zone in self._prev_track_zone.items():
            if old_track_id not in current_track_ids and old_zone is not None:
                events.append(ZoneMembershipEvent(old_track_id, old_zone, "exit", timestamp))

        zone_occupancy = {zone.id: 0 for zone in self.zones}
        for zone_id in track_zone.values():
            if zone_id is not None:
                zone_occupancy[zone_id] += 1

        exit_occupancy = {exit_.id: 0 for exit_ in self.exits}
        for exit_id in track_exit.values():
            if exit_id is not None:
                exit_occupancy[exit_id] += 1

        danger_zone_occupancy = sum(zone_occupancy[zone.id] for zone in self.zones if zone.type == "danger")

        self._prev_track_zone = track_zone

        return ZoneState(
            timestamp=timestamp,
            camera_id=self.camera_id,
            track_zone=track_zone,
            track_exit=track_exit,
            zone_occupancy=zone_occupancy,
            exit_occupancy=exit_occupancy,
            danger_zone_occupancy=danger_zone_occupancy,
            events=events,
        )
