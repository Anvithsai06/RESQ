"""
Renders the demo video with real detections and track IDs drawn on it, for
the dashboard's scene panel.

Uses the real two-model detector and the real ByteTracker — every box and
ID in the output comes from actual inference. Nothing is simulated.

    python3 scripts/render_annotated_demo.py

Output: data/demo/annotated_scene.mp4 (gitignored, like all of data/).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config.settings import settings  # noqa: E402
from vision.detection.detector import create_multi_model_detector  # noqa: E402
from vision.tracking.byte_tracker import ByteTracker  # noqa: E402
from vision.video.pipeline import run_vertical_slice  # noqa: E402

OUTPUT_PATH = "data/demo/annotated_scene.mp4"


def main() -> int:
    video_path = Path(settings.demo_video_path)
    if not video_path.is_file():
        print(f"ERROR: demo video not found at {video_path}", file=sys.stderr)
        return 1

    for label, model_path in (("person", settings.yolo_model_path), ("fire/smoke", settings.hazard_yolo_model_path)):
        if not Path(model_path).is_file():
            print(f"ERROR: {label} model weights not found at {model_path}", file=sys.stderr)
            return 1

    detector = create_multi_model_detector(
        person_model_path=settings.yolo_model_path,
        hazard_model_path=settings.hazard_yolo_model_path,
        model_versions_path="configs/model_versions.json",
        confidence_threshold=settings.yolo_confidence_threshold,
    )
    tracker = ByteTracker(camera_id="CAM-01")

    print(f"Rendering {video_path} -> {OUTPUT_PATH} (real dual-model inference)...")
    frames = run_vertical_slice(
        video_path=str(video_path),
        camera_id="CAM-01",
        detector=detector,
        tracker=tracker,
        output_path=OUTPUT_PATH,
        sample_rate=settings.frame_sample_rate,
    )
    print(f"Done — {frames} annotated frames written to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
