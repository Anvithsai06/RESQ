"""
Central configuration loader — WORKFLOW.md Phase 1.

Single source of truth for env-driven paths/settings, read once via
python-dotenv. Every other module (vision/, intelligence/, backend/) should
import `settings` from here rather than reading os.environ directly.

Kept as a plain dataclass rather than pydantic-settings, since the latter
isn't in requirements.txt and this doesn't need validation beyond defaults.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


@dataclass(frozen=True)
class Settings:
    # Supabase
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_service_role_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

    # Vision / models
    demo_video_path: str = field(default_factory=lambda: os.getenv("DEMO_VIDEO_PATH", "data/demo/emergency_scene.mp4"))
    frame_sample_rate: int = field(default_factory=lambda: _env_int("FRAME_SAMPLE_RATE", 5))
    yolo_model_path: str = field(default_factory=lambda: os.getenv("YOLO_MODEL_PATH", "models/yolo/best.pt"))
    hazard_yolo_model_path: str = field(default_factory=lambda: os.getenv("HAZARD_YOLO_MODEL_PATH", "models/yolo/fire_smoke.pt"))
    yolo_confidence_threshold: float = field(default_factory=lambda: _env_float("YOLO_CONFIDENCE_THRESHOLD", 0.5))
    bytetrack_config_path: str = field(default_factory=lambda: os.getenv("BYTETRACK_CONFIG_PATH", "configs/bytetrack.yaml"))

    # Building / scene config
    building_config_path: str = field(default_factory=lambda: os.getenv("BUILDING_CONFIG_PATH", "building/building.json"))
    cameras_config_path: str = field(default_factory=lambda: os.getenv("CAMERAS_CONFIG_PATH", "building/cameras.json"))
    zones_config_path: str = field(default_factory=lambda: os.getenv("ZONES_CONFIG_PATH", "building/zones.json"))
    exits_config_path: str = field(default_factory=lambda: os.getenv("EXITS_CONFIG_PATH", "building/exits.json"))
    emergency_contacts_config_path: str = field(
        default_factory=lambda: os.getenv("EMERGENCY_CONTACTS_CONFIG_PATH", "building/emergency_contacts.json")
    )
    thresholds_config_path: str = field(default_factory=lambda: os.getenv("THRESHOLDS_CONFIG_PATH", "configs/thresholds.json"))

    # Notification engine
    notification_provider: str = field(default_factory=lambda: os.getenv("NOTIFICATION_PROVIDER", "mock"))


settings = Settings()
