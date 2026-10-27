"""
Integration — WORKFLOW.md Phase 14.

The real, single-process pipeline:

    Video → Detection → Tracking → Zone → Temporal → Exit State →
    Priority → Incident State → Notification → Dashboard

Wires every phase's real implementation together, publishes each tick's
Incident State into backend/api/incident.py's store (what the dashboard
polls), and dispatches notifications through
intelligence/notification/notifier.py.

Requires, none of which are bundled in this repo (see README/.gitignore):
  - A demo video at settings.demo_video_path — WORKFLOW.md Phase 2.
  - `pip install ultralytics` and weights for BOTH detection models at
    settings.yolo_model_path (person) and settings.hazard_yolo_model_path
    (fire/smoke) — WORKFLOW.md Phase 3.

Without those, `run_default_pipeline()` raises a clear error rather than
fabricating detections. For local dashboard testing without real weights,
use backend/dev/seed_demo_incident.py instead — it exercises everything
downstream of detection with synthetic input.

Run via: RESQ_RUN_PIPELINE=true uvicorn backend.main:app --reload
(a single command, per WORKFLOW.md Phase 14 — the pipeline runs in a
background thread inside the same process serving the dashboard).
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable

from backend.api.incident import publish_incident_state
from backend.config.cameras import CameraConfig, load_cameras
from backend.config.settings import settings
from intelligence.incident.state import IncidentStateBuilder
from intelligence.incident.state import NotificationStatus as IncidentNotificationStatus
from intelligence.notification.notifier import (
    EmergencyContactsDirectory,
    InMemoryNotificationLogger,
    NotificationDispatcher,
    NotificationEngine,
    NotificationLogger,
    SupabaseNotificationLogger,
)
from intelligence.priority.engine import PriorityEngine
from intelligence.temporal.engine import TemporalEngine
from intelligence.temporal.exit_state import ExitStateEngine
from vision.detection.detector import Detector, create_multi_model_detector
from vision.tracking.byte_tracker import ByteTracker
from vision.video.ingestion import VideoSource
from vision.zones.engine import Zone, ZoneEngine


def _load_building_id(building_config_path: str) -> str:
    with open(building_config_path) as f:
        return json.load(f)["building_id"]


def _load_zone_types(zones_config_path: str) -> dict[str, str]:
    return {zone.id: zone.type for zone in Zone.from_file(zones_config_path)}


def _build_notification_logger(building_id: str) -> NotificationLogger:
    """Uses Supabase if configured (backend/config/settings.py), otherwise
    falls back to logging in-memory only — never blocks startup on a
    missing/unreachable Supabase project."""
    if settings.supabase_url and settings.supabase_service_role_key:
        try:
            from supabase import create_client

            client = create_client(settings.supabase_url, settings.supabase_service_role_key)
            return SupabaseNotificationLogger(client, building_id=building_id)
        except Exception as exc:  # missing `supabase` package, bad credentials, network, etc.
            print(f"[pipeline] Could not connect to Supabase ({exc}); logging notifications in-memory only.")
    return InMemoryNotificationLogger()


def run_pipeline(
    detector: Detector,
    camera_id: str = "CAM-01",
    video_path: str | None = None,
    sample_rate: int | None = None,
    realtime: bool = False,
    loop: bool = False,
    zones_config_path: str | None = None,
    exits_config_path: str | None = None,
    on_tick: Callable[[int, int | None], None] | None = None,
) -> None:
    """Runs the full real pipeline against one video, publishing each
    tick's Incident State and dispatching notifications. `detector` is
    injected so this stays testable without real YOLO weights — see
    tests/integration/test_full_pipeline.py.

    `realtime` paces each tick to the video's own timestamps so a responder
    watching the dashboard sees the incident develop at true speed instead
    of the whole clip completing in a few seconds. `loop` replays the clip
    continuously for an unattended demo. Both only affect *pacing* — the
    detections, tracking and scoring are identical either way.

    `zones_config_path`/`exits_config_path` default to the single-camera
    settings-driven paths (unchanged original behavior) — pass a specific
    camera's own paths (see backend/config/cameras.py) to run this against
    a different camera, whose zone/exit polygons live in that camera's own
    image space and must not be assumed to match another camera's.

    `on_tick(ticks_processed, total_ticks)` is called after every processed
    frame — used by backend/api/uploads.py to report real progress on a
    manually-uploaded video rather than pretending the result is instant.
    `total_ticks` is None if it couldn't be determined up front.
    """
    video_path = video_path or settings.demo_video_path
    sample_rate = sample_rate if sample_rate is not None else settings.frame_sample_rate
    zones_config_path = zones_config_path or settings.zones_config_path
    exits_config_path = exits_config_path or settings.exits_config_path

    def fresh_stateful_engines():
        """Per-pass state. Rebuilt for each replay so track IDs, temporal
        history, and the priority engine's hazard growth-rate window never
        carry across passes — every pass is an independent, honest
        processing of the clip."""
        return (
            ByteTracker(camera_id=camera_id),
            ZoneEngine.from_files(zones_config_path, exits_config_path, camera_id=camera_id),
            TemporalEngine.from_thresholds_file(settings.thresholds_config_path, camera_id=camera_id),
            ExitStateEngine.from_config_files(settings.thresholds_config_path, exits_config_path),
            IncidentStateBuilder(),
            PriorityEngine.from_config_files(
                settings.thresholds_config_path, "configs/model_versions.json", zones_config_path
            ),
        )

    building_id = _load_building_id(settings.building_config_path)
    zone_types = _load_zone_types(zones_config_path)
    contacts = EmergencyContactsDirectory.from_file(settings.emergency_contacts_config_path)
    notification_dispatcher = NotificationDispatcher(
        NotificationEngine(), contacts, zone_types, building_id, logger=_build_notification_logger(building_id)
    )

    with open(settings.thresholds_config_path) as f:
        notif_cfg = json.load(f)["notification"]

    tracker, zone_engine, temporal_engine, exit_state_engine, incident_builder, priority_engine = fresh_stateful_engines()

    while True:
        wall_start = time.monotonic()
        with VideoSource(video_path, camera_id=camera_id, sample_rate=sample_rate) as source:
            total_ticks = (source.total_frames // sample_rate) + 1 if source.total_frames > 0 else None
            ticks_processed = 0
            for frame in source.frames():
                if realtime:
                    # Pace to the clip's own timeline. If inference is slower
                    # than real time we simply fall behind rather than dropping
                    # frames — every frame still gets fully processed.
                    behind = frame.timestamp - (time.monotonic() - wall_start)
                    if behind > 0:
                        time.sleep(behind)

                detections = detector.detect(frame)
                tracks = tracker.update(detections, frame.timestamp)
                zone_state = zone_engine.update(tracks, frame.timestamp)
                temporal_state = temporal_engine.update(tracks, detections, zone_state, frame.timestamp)
                exit_states = exit_state_engine.update(temporal_state.exits, tracks, zone_state.track_exit)
                priority_result = priority_engine.update(
                    zone_state, temporal_state, exit_states, tracks, frame.timestamp
                )
                incident_state = incident_builder.update(
                    zone_state, temporal_state, exit_states, priority_result, tracks, frame.timestamp
                )

                outcome = notification_dispatcher.evaluate_and_dispatch(
                    incident_state,
                    critical_threshold=notif_cfg["critical_priority_threshold"],
                    persistence_seconds=notif_cfg["notification_persistence_seconds"],
                    cooldown_seconds=notif_cfg["notification_cooldown_seconds"],
                    now=frame.timestamp,
                )
                notification_status = IncidentNotificationStatus(
                    status=outcome.status.value,
                    reason=outcome.reason,
                    recipient_name=", ".join(r.name for r in outcome.recipients) if outcome.recipients else None,
                    sent_at=outcome.dispatched_at,
                )
                incident_builder.set_notification(notification_status)
                # This tick's published view, not just future ticks'.
                incident_state.notification = notification_status
                # Alert latching (Task 1.4): keep the incident visibly
                # flagged as an active alert for notification_persistence_seconds
                # after it fires, even if priority dips on a later tick.
                # `band`/`priority` above are untouched — always the honest
                # instantaneous value.
                incident_state.alert_active = notification_dispatcher.engine.is_alert_latched(
                    notif_cfg["notification_persistence_seconds"], now=frame.timestamp
                )

                publish_incident_state(incident_state)

                ticks_processed += 1
                if on_tick is not None:
                    on_tick(ticks_processed, total_ticks)

        if not loop:
            break
        tracker, zone_engine, temporal_engine, exit_state_engine, incident_builder, priority_engine = fresh_stateful_engines()

    notification_dispatcher.shutdown()


def run_default_pipeline(camera_id: str = "CAM-01") -> None:
    """Builds the real, two-model YOLO-backed detector (person + fire/smoke)
    from settings and runs the full pipeline. Raises a clear error — rather
    than fabricating detections — if either model's weights or ultralytics
    aren't available."""
    try:
        detector = create_multi_model_detector(
            person_model_path=settings.yolo_model_path,
            hazard_model_path=settings.hazard_yolo_model_path,
            model_versions_path="configs/model_versions.json",
            confidence_threshold=settings.yolo_confidence_threshold,
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not initialize the YOLO detectors — install `ultralytics` and place weights at "
            f"{settings.yolo_model_path} (person model) and {settings.hazard_yolo_model_path} "
            "(fire/smoke model) — see WORKFLOW.md Phase 3. For local dashboard testing without real "
            "weights, use backend/dev/seed_demo_incident.py instead."
        ) from exc

    # Demo pacing, opt-in via env. These affect only how fast frames are fed
    # through — never what is detected or scored.
    realtime = os.getenv("RESQ_PIPELINE_REALTIME", "false").lower() == "true"
    loop = os.getenv("RESQ_PIPELINE_LOOP", "false").lower() == "true"
    run_pipeline(detector, camera_id=camera_id, realtime=realtime, loop=loop)


class _LockedDetector:
    """Serializes access to a shared Detector across camera threads.

    A single ultralytics.YOLO instance isn't documented as safe for
    concurrent inference calls from multiple threads, and this repo hasn't
    load-tested it — rather than assume it's fine, every call goes through
    one lock. With today's config only one camera has real footage, so this
    lock is never actually contended; it exists for the moment a second
    real camera is added. Satisfies the same YoloBackend-adjacent `.detect`
    interface as vision.detection.detector.Detector, so it's a drop-in
    substitute at each camera thread's call sites."""

    def __init__(self, detector: Detector):
        self._detector = detector
        self._lock = threading.Lock()

    def detect(self, frame):
        with self._lock:
            return self._detector.detect(frame)


_shared_detector_lock = threading.Lock()
_shared_locked_detector: _LockedDetector | None = None


def get_shared_detector() -> "_LockedDetector":
    """Lazily builds and caches the real two-model detector behind a
    _LockedDetector, shared by the startup multi-camera pipeline and any
    later on-demand upload processing (backend/api/uploads.py, Task 3) —
    avoids loading the same weights twice and gives every caller the same
    thread-safety guarantee."""
    global _shared_locked_detector
    with _shared_detector_lock:
        if _shared_locked_detector is None:
            detector = create_multi_model_detector(
                person_model_path=settings.yolo_model_path,
                hazard_model_path=settings.hazard_yolo_model_path,
                model_versions_path="configs/model_versions.json",
                confidence_threshold=settings.yolo_confidence_threshold,
            )
            _shared_locked_detector = _LockedDetector(detector)
        return _shared_locked_detector


def run_camera_pipeline(camera: CameraConfig, detector: Detector, realtime: bool = False, loop: bool = False) -> None:
    """Runs the existing single-camera `run_pipeline` against one
    CameraConfig's own video source and zone/exit config — the "each
    camera gets its own instance of the existing pipeline objects" seam.
    Nothing about the pipeline itself changes per camera; only which
    files/video feed it."""
    run_pipeline(
        detector,
        camera_id=camera.camera_id,
        video_path=camera.source,
        realtime=realtime,
        loop=loop,
        zones_config_path=camera.zones_config_path,
        exits_config_path=camera.exits_config_path,
    )


def run_all_cameras_pipeline(cameras_config_path: str = "building/cameras.json") -> None:
    """Multi-camera entrypoint (Task 2): runs the real pipeline for every
    camera in building/cameras.json that actually has a video file at its
    configured `source` — one thread per camera, each a fully independent
    instance of the same single-camera pipeline (own tracker, own zone/
    temporal/priority engines, own Incident State).

    A camera without real footage (source file missing) is skipped with a
    clear log line — never silently, never by fabricating detections for
    it. This is what backend/main.py runs for RESQ_RUN_PIPELINE=true; with
    today's config (only CAM-01 has real footage) it behaves identically
    to running just CAM-01, so this is a strict superset of the original
    single-camera behavior, not a replacement for it.
    """
    try:
        locked_detector = get_shared_detector()
    except Exception as exc:
        raise RuntimeError(
            "Could not initialize the YOLO detectors — install `ultralytics` and place weights at "
            f"{settings.yolo_model_path} (person model) and {settings.hazard_yolo_model_path} "
            "(fire/smoke model) — see WORKFLOW.md Phase 3."
        ) from exc

    realtime = os.getenv("RESQ_PIPELINE_REALTIME", "false").lower() == "true"
    loop = os.getenv("RESQ_PIPELINE_LOOP", "false").lower() == "true"

    cameras = load_cameras(cameras_config_path)
    threads = []
    for camera in cameras:
        if not camera.source_available:
            print(f"[pipeline] Skipping {camera.camera_id} ({camera.name}) — no video at {camera.source!r}.")
            continue
        print(f"[pipeline] Starting {camera.camera_id} ({camera.name}) on {camera.source}")
        # Everything stateful (tracker, zone/temporal/priority engines) is
        # constructed fresh per camera inside run_camera_pipeline; only
        # detection inference is shared, and that's serialized above.
        t = threading.Thread(
            target=run_camera_pipeline,
            args=(camera, locked_detector),
            kwargs={"realtime": realtime, "loop": loop},
            daemon=True,
        )
        t.start()
        threads.append(t)

    if not threads:
        raise RuntimeError(
            "No configured camera has a video file at its `source` path — nothing to run. "
            "See building/cameras.json."
        )

    for t in threads:
        t.join()


if __name__ == "__main__":
    run_default_pipeline()
