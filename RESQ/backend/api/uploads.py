"""
Manual video upload — Task 3 (live demo / jury evaluation).

Lets an operator supply a video file for a configured camera at demo time,
instead of only the baked-in demo video. An uploaded clip goes through the
exact same real pipeline (detection → tracking → zones → temporal →
priority → incident state → notification) as any other camera — nothing
here fabricates a shortcut result. Processing runs in the background; the
frontend polls GET /cameras/{camera_id}/upload/status rather than
assuming instant availability.

Validation is real, not just an extension check: the file is opened with
vision/video/ingestion.py's VideoSource (the same code every other video
in this app goes through), so a renamed non-video file is rejected the
same way a corrupt one would be. If the camera declares a resolution
(building/cameras.json), an uploaded clip must match it — zone/exit
polygons are calibrated pixel coordinates for one specific resolution and
silently misapplying them to a different one would be dishonest, not
convenient.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config.cameras import get_camera, set_source_override
from backend.config.settings import settings
from vision.detection.detector import Detector
from vision.video.ingestion import VideoSource

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500MB — generous for a short demo clip
UPLOAD_DIR = Path("data/uploads")


@dataclass
class UploadJob:
    camera_id: str
    status: str  # "validating" | "processing" | "ready" | "failed"
    detail: str | None = None
    video_path: str | None = None
    resolution: tuple[int, int] | None = None
    total_ticks: int | None = None
    ticks_processed: int = 0
    started_at: float = field(default_factory=time.time)


_lock = threading.Lock()
_jobs: dict[str, UploadJob] = {}


def get_job(camera_id: str) -> UploadJob | None:
    with _lock:
        return _jobs.get(camera_id)


def _set_job(job: UploadJob) -> None:
    with _lock:
        _jobs[job.camera_id] = job


def _reset_for_tests() -> None:
    global _jobs
    with _lock:
        _jobs = {}


def _run_processing_job(camera_id: str, video_path: str, detector: Detector, sample_rate: int) -> None:
    """Runs the real single-camera pipeline against the uploaded video, in
    the background. `detector` is injected so tests can exercise this
    without real YOLO weights — see tests/unit/test_uploads.py."""
    from backend.pipeline import run_pipeline  # local import: avoids a hard import cycle at module load

    camera = get_camera(camera_id)
    job = get_job(camera_id)
    if job is None:
        return
    job.status = "processing"
    _set_job(job)

    def on_tick(ticks_processed: int, total_ticks: int | None) -> None:
        job.ticks_processed = ticks_processed
        job.total_ticks = total_ticks
        _set_job(job)

    try:
        run_pipeline(
            detector,
            camera_id=camera_id,
            video_path=video_path,
            sample_rate=sample_rate,
            zones_config_path=camera.zones_config_path if camera else None,
            exits_config_path=camera.exits_config_path if camera else None,
            on_tick=on_tick,
        )
        job.status = "ready"
        job.detail = None
    except Exception as exc:  # a real, uploaded video can legitimately fail mid-processing
        job.status = "failed"
        job.detail = str(exc)
    _set_job(job)


def _default_detector() -> Detector:
    from backend.pipeline import get_shared_detector

    return get_shared_detector()


def handle_upload(
    camera_id: str,
    filename: str,
    content: bytes,
    detector: Optional[Detector] = None,
    _start_background_job: bool = True,
) -> UploadJob:
    """Core upload handling, separated from the FastAPI route so tests can
    call it directly with an injected fake detector — no real weights
    required, same pattern as vision/detection/detector.py's FakeBackend
    tests elsewhere in this repo. Raises HTTPException on any validation
    failure (bad extension, unreadable file, resolution mismatch)."""
    camera = get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"No camera configured with id {camera_id!r}")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {extension!r} — allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit")

    job = UploadJob(camera_id=camera_id, status="validating")
    _set_job(job)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{camera_id}_{uuid.uuid4().hex[:8]}{extension}"
    dest.write_bytes(content)

    try:
        with VideoSource(dest, camera_id=camera_id, sample_rate=1) as probe:
            resolution = (probe.frame_width, probe.frame_height)
            total_frames = probe.total_frames
    except Exception as exc:
        dest.unlink(missing_ok=True)
        job.status = "failed"
        job.detail = f"Could not read video: {exc}"
        _set_job(job)
        raise HTTPException(status_code=400, detail=job.detail) from exc

    if camera.resolution is not None and tuple(camera.resolution) != resolution:
        dest.unlink(missing_ok=True)
        job.status = "failed"
        job.detail = (
            f"Video resolution {resolution[0]}x{resolution[1]} does not match {camera_id}'s configured "
            f"resolution {camera.resolution[0]}x{camera.resolution[1]} — zone/exit polygons are calibrated "
            "pixel coordinates and would not align with a different resolution."
        )
        _set_job(job)
        raise HTTPException(status_code=400, detail=job.detail)

    set_source_override(camera_id, str(dest))

    job.video_path = str(dest)
    job.resolution = resolution
    job.total_ticks = (total_frames // settings.frame_sample_rate) + 1 if total_frames > 0 else None
    job.status = "processing"
    _set_job(job)

    if _start_background_job:
        active_detector = detector if detector is not None else _default_detector()
        thread = threading.Thread(
            target=_run_processing_job,
            args=(camera_id, str(dest), active_detector, settings.frame_sample_rate),
            daemon=True,
        )
        thread.start()

    return job


@router.post("/{camera_id}/upload")
async def upload_camera_video(camera_id: str, file: UploadFile = File(...)):
    content = await file.read()
    job = handle_upload(camera_id, file.filename or "upload", content)
    return {
        "camera_id": job.camera_id,
        "status": job.status,
        "resolution": job.resolution,
        "total_ticks": job.total_ticks,
    }


@router.get("/{camera_id}/upload/status")
def get_upload_status(camera_id: str):
    job = get_job(camera_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No upload job for {camera_id!r}")
    return {
        "camera_id": job.camera_id,
        "status": job.status,
        "detail": job.detail,
        "resolution": job.resolution,
        "ticks_processed": job.ticks_processed,
        "total_ticks": job.total_ticks,
    }
