"""
Building configuration API — serves the human-curated config the dashboard
needs to draw the situational view (zones, exits, cameras) without
bundling building/*.json into the frontend build. Read-only, straight
passthrough of the config files — RESQ does not infer or edit this
configuration at runtime.

`/zones`, `/exits` (no camera_id) are kept exactly as they always were —
CAM-01 only — for backward compatibility. Multi-camera consumers use
`/cameras`, `/cameras/{camera_id}/zones`, `/cameras/{camera_id}/exits`.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from backend.config.cameras import get_camera, load_cameras
from backend.config.settings import settings

router = APIRouter()


@router.get("/zones")
def get_zones():
    with open(settings.zones_config_path) as f:
        return json.load(f)


@router.get("/exits")
def get_exits():
    with open(settings.exits_config_path) as f:
        return json.load(f)


@router.get("/building")
def get_building():
    with open(settings.building_config_path) as f:
        return json.load(f)


@router.get("/cameras")
def get_cameras():
    """Every configured camera plus whether it actually has a video file
    (never fabricated — a camera with `source_available: false` really has
    no footage yet)."""
    cameras = load_cameras()
    return [{**asdict(c), "source_available": c.source_available} for c in cameras]


@router.get("/cameras/{camera_id}/zones")
def get_camera_zones(camera_id: str):
    camera = get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"No camera configured with id {camera_id!r}")
    with open(camera.zones_config_path) as f:
        return json.load(f)


@router.get("/cameras/{camera_id}/exits")
def get_camera_exits(camera_id: str):
    camera = get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"No camera configured with id {camera_id!r}")
    with open(camera.exits_config_path) as f:
        return json.load(f)
