"""
RESQ backend entrypoint.

FastAPI app exposing:
- incident state (current + timeline)
- annotated video / detection stream endpoints
- building/zone/exit config
- notification status/log

Run with: uvicorn backend.main:app --reload

Two opt-in background modes, both off by default, mutually exclusive:

  RESQ_RUN_PIPELINE=true              Runs the real Phase 14 pipeline
                                       (backend/pipeline.py) for every
                                       camera in building/cameras.json that
                                       actually has a video file — video ->
                                       YOLO -> ByteTrack -> ... ->
                                       dashboard, independently per camera.
                                       Requires YOLO weights (see
                                       WORKFLOW.md Phases 2-3); raises a
                                       clear error if they're missing. With
                                       only CAM-01 configured (today's
                                       state), this behaves identically to
                                       running just CAM-01.

  RESQ_DEV_SEED_DEMO_INCIDENT=true    Streams a synthetic escalating
                                       scenario through the intelligence
                                       stack instead (backend/dev/
                                       seed_demo_incident.py) — for
                                       exercising the dashboard without
                                       real weights/video.
"""
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import config, incident, media, uploads


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("RESQ_RUN_PIPELINE", "false").lower() == "true":
        from backend.pipeline import run_all_cameras_pipeline

        threading.Thread(target=run_all_cameras_pipeline, daemon=True).start()
    elif os.getenv("RESQ_DEV_SEED_DEMO_INCIDENT", "false").lower() == "true":
        from backend.dev.seed_demo_incident import run as run_demo_seed

        threading.Thread(target=run_demo_seed, daemon=True).start()
    yield


app = FastAPI(
    title="RESQ API",
    description="Real-Time Emergency Scene Intelligence — backend API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(incident.router, prefix="/incident", tags=["incident"])
app.include_router(config.router, prefix="/config", tags=["config"])
app.include_router(media.router, prefix="/media", tags=["media"])
app.include_router(uploads.router, prefix="/cameras", tags=["uploads"])

# Notification status is surfaced through Incident State (see
# intelligence/incident/state.py's `notification` field) rather than a
# separate REST surface — the dashboard's status line reads it from
# /incident/current like everything else.
