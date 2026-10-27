"""
Camera registry — WORKFLOW.md Phase 5, generalized for multi-camera.

Loads building/cameras.json into typed CameraConfig objects. Each camera
carries its own resolution, video source, and zones/exits config paths —
RESQ never assumes cameras share a resolution or zone set (zone/exit
polygons are pixel coordinates in one specific camera's own image space).

Also holds the in-memory source override used by manual video upload
(backend/api/uploads.py, Task 3) — a judge-supplied clip for a camera
takes effect for that camera's `source` everywhere (pipeline, media
routes) without rewriting building/cameras.json on disk. Lives here rather
than in uploads.py so pipeline.py and media.py can both read it without a
circular import.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CameraConfig:
    camera_id: str
    name: str
    resolution: tuple[int, int] | None
    source: str
    zones_config_path: str
    exits_config_path: str
    covered_zones: list[str]
    covered_exits: list[str]

    @property
    def source_available(self) -> bool:
        return Path(self.source).is_file()


_override_lock = threading.Lock()
_source_overrides: dict[str, str] = {}


def set_source_override(camera_id: str, video_path: str) -> None:
    with _override_lock:
        _source_overrides[camera_id] = video_path


def clear_source_override(camera_id: str) -> None:
    with _override_lock:
        _source_overrides.pop(camera_id, None)


def _reset_overrides_for_tests() -> None:
    global _source_overrides
    with _override_lock:
        _source_overrides = {}


def load_cameras(cameras_config_path: str | Path = "building/cameras.json") -> list[CameraConfig]:
    with open(cameras_config_path) as f:
        config = json.load(f)

    with _override_lock:
        overrides = dict(_source_overrides)

    cameras = []
    for c in config["cameras"]:
        resolution = tuple(c["resolution"]) if c.get("resolution") else None
        camera_id = c["camera_id"]
        cameras.append(
            CameraConfig(
                camera_id=camera_id,
                name=c.get("name", camera_id),
                resolution=resolution,
                source=overrides.get(camera_id, c["source"]),
                zones_config_path=c["zones_config_path"],
                exits_config_path=c["exits_config_path"],
                covered_zones=c.get("covered_zones", []),
                covered_exits=c.get("covered_exits", []),
            )
        )
    return cameras


def get_camera(camera_id: str, cameras_config_path: str | Path = "building/cameras.json") -> CameraConfig | None:
    for camera in load_cameras(cameras_config_path):
        if camera.camera_id == camera_id:
            return camera
    return None
