"""
Media API — serves scene video to the responder dashboard, generalized for
multi-camera.

Serves real files from disk only. If a file hasn't been produced yet the
route returns 404 and the dashboard shows an honest "unavailable" state —
nothing here fabricates or placeholders a video.

The annotated video (bounding boxes + track IDs drawn by
vision/video/annotate.py) is produced by running the vertical-slice
pipeline; see scripts/render_annotated_demo.py.

`/annotated`, `/source`, `/status` (no camera_id) are kept exactly as they
always were — CAM-01 only — for backward compatibility. Multi-camera
consumers use the `/{camera_id}/...` routes below.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.config.cameras import get_camera
from backend.config.settings import settings

router = APIRouter()

ANNOTATED_VIDEO_PATH = os.getenv("ANNOTATED_VIDEO_PATH", "data/demo/annotated_scene.mp4")
DEFAULT_CAMERA_ID = "CAM-01"


def _annotated_path_for(camera_id: str) -> str:
    """CAM-01 keeps its original fixed filename (already-rendered files
    stay valid); every other camera gets the `annotated_{camera_id}.mp4`
    convention — see scripts/render_annotated_demo.py."""
    if camera_id == DEFAULT_CAMERA_ID:
        return ANNOTATED_VIDEO_PATH
    return f"data/demo/annotated_{camera_id}.mp4"


def _serve(path: str, missing_detail: str) -> FileResponse:
    file_path = Path(path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=missing_detail)
    return FileResponse(file_path, media_type="video/mp4")


def _source_path_for(camera_id: str) -> str:
    # Always resolve through get_camera() first — it applies any upload
    # override (backend/config/cameras.py, Task 3) for every camera,
    # CAM-01 included. settings.demo_video_path is only a defensive
    # fallback if CAM-01 somehow isn't in building/cameras.json.
    camera = get_camera(camera_id)
    if camera is not None:
        return camera.source
    if camera_id == DEFAULT_CAMERA_ID:
        return settings.demo_video_path
    raise HTTPException(status_code=404, detail=f"No camera configured with id {camera_id!r}")


@router.get("/annotated")
def get_annotated_video():
    return _serve(
        _annotated_path_for(DEFAULT_CAMERA_ID),
        "Annotated video not rendered yet — run scripts/render_annotated_demo.py",
    )


@router.get("/source")
def get_source_video():
    return _serve(_source_path_for(DEFAULT_CAMERA_ID), "Source demo video not found")


@router.get("/status")
def get_media_status():
    return {
        "annotated_available": Path(_annotated_path_for(DEFAULT_CAMERA_ID)).is_file(),
        "source_available": Path(_source_path_for(DEFAULT_CAMERA_ID)).is_file(),
    }


@router.get("/{camera_id}/annotated")
def get_camera_annotated_video(camera_id: str):
    return _serve(
        _annotated_path_for(camera_id),
        f"Annotated video not rendered yet for {camera_id} — run scripts/render_annotated_demo.py",
    )


@router.get("/{camera_id}/source")
def get_camera_source_video(camera_id: str):
    return _serve(_source_path_for(camera_id), f"Source video not found for {camera_id}")


@router.get("/{camera_id}/status")
def get_camera_media_status(camera_id: str):
    camera = get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"No camera configured with id {camera_id!r}")
    return {
        "camera_id": camera_id,
        "name": camera.name,
        "annotated_available": Path(_annotated_path_for(camera_id)).is_file(),
        "source_available": camera.source_available,
    }
