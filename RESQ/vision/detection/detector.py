"""
Detection — WORKFLOW.md Phase 3.

Detects people and validated hazard classes:

    Frame → YOLO → Detection[]

Only classes listed in configs/model_versions.json (validated_classes +
experimental_classes) are ever returned — an unlisted class from the raw
model output is dropped, not surfaced. This keeps "validated hazard class"
an explicit, human-curated set rather than whatever the model happens to
output. Each Detection carries a `validated` flag so downstream stages
(priority, notification) can distinguish a validated class from an
experimental one when reasoning about confidence/uncertainty.

The YOLO backend is swappable behind `YoloBackend` so this module is
testable without model weights present (see UltralyticsBackend vs. a fake
backend in tests).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

BBox = tuple[float, float, float, float]  # x1, y1, x2, y2


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: BBox
    timestamp: float
    camera_id: str
    validated: bool  # False if class_name is only in experimental_classes


class ModelClassConfig:
    """Loads the allowed detection classes from configs/model_versions.json.

    A class not listed under validated_classes or experimental_classes is
    never returned by Detector — RESQ does not surface an unvetted class
    just because the underlying model happened to output it.
    """

    def __init__(self, validated_classes: set[str], experimental_classes: set[str]):
        self.validated_classes = validated_classes
        self.experimental_classes = experimental_classes

    @classmethod
    def from_file(cls, path: str | Path) -> "ModelClassConfig":
        with open(path) as f:
            config = json.load(f)
        detector_config = config["detector"]
        return cls(
            validated_classes=set(detector_config.get("validated_classes", [])),
            experimental_classes=set(detector_config.get("experimental_classes", [])),
        )

    def is_allowed(self, class_name: str) -> bool:
        return class_name in self.validated_classes or class_name in self.experimental_classes

    def is_validated(self, class_name: str) -> bool:
        return class_name in self.validated_classes


class YoloBackend(Protocol):
    """Narrow interface a detection backend must satisfy — decouples the
    filtering/postprocessing logic below from any specific YOLO library
    version or API."""

    def infer(
        self, image: np.ndarray, confidence_threshold: float
    ) -> list[tuple[str, float, BBox]]:
        """Return raw (class_name, confidence, bbox) tuples, unfiltered."""
        ...


class UltralyticsBackend:
    """Real backend — wraps `ultralytics.YOLO`. Requires model weights on
    disk (see configs/model_versions.json → detector.weights_path)."""

    def __init__(self, model_path: str | Path):
        from ultralytics import YOLO  # imported lazily: not required for tests/fake backends

        self._model = YOLO(str(model_path))

    def infer(
        self, image: np.ndarray, confidence_threshold: float
    ) -> list[tuple[str, float, BBox]]:
        results = self._model(image, conf=confidence_threshold, verbose=False)
        raw: list[tuple[str, float, BBox]] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                cls_id = int(box.cls[0])
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                raw.append((names[cls_id], confidence, (x1, y1, x2, y2)))
        return raw


class Detector:
    """Runs a YOLO backend on a frame and returns filtered, explainable
    Detection objects — only validated/experimental classes, above the
    configured confidence threshold."""

    def __init__(
        self,
        backend: YoloBackend,
        class_config: ModelClassConfig,
        confidence_threshold: float,
    ):
        self._backend = backend
        self._class_config = class_config
        self._confidence_threshold = confidence_threshold

    def detect(self, frame) -> list[Detection]:
        """`frame` is a vision.video.ingestion.Frame."""
        raw = self._backend.infer(frame.image, self._confidence_threshold)
        detections: list[Detection] = []
        for class_name, confidence, bbox in raw:
            if confidence < self._confidence_threshold:
                continue
            if not self._class_config.is_allowed(class_name):
                continue
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=bbox,
                    timestamp=frame.timestamp,
                    camera_id=frame.camera_id,
                    validated=self._class_config.is_validated(class_name),
                )
            )
        return detections


def create_default_detector(
    model_path: str | Path, model_versions_path: str | Path, confidence_threshold: float
) -> Detector:
    """Factory used by the integration pipeline (Phase 14) — builds a
    Detector against the real ultralytics backend and the configured class
    allowlist."""
    return Detector(
        backend=UltralyticsBackend(model_path),
        class_config=ModelClassConfig.from_file(model_versions_path),
        confidence_threshold=confidence_threshold,
    )


class MultiModelBackend:
    """Runs two YoloBackends (e.g. a person-detection model and a
    fire/smoke-detection model) on the same frame and merges their raw
    output — WORKFLOW.md Phase 3's two-model extension.

    Both sub-backends already return the standard (class_name, confidence,
    bbox) tuple format, so "normalizing into the existing schema" is
    exactly the concatenation below — no per-model translation is needed
    because that normalization already happens inside each UltralyticsBackend.
    Detector's existing class allowlist/confidence filtering (unchanged)
    applies uniformly to the merged output, regardless of which sub-backend
    produced a given detection.
    """

    def __init__(self, person_backend: YoloBackend, hazard_backend: YoloBackend):
        self._person_backend = person_backend
        self._hazard_backend = hazard_backend

    def infer(
        self, image: np.ndarray, confidence_threshold: float
    ) -> list[tuple[str, float, BBox]]:
        person_raw = self._person_backend.infer(image, confidence_threshold)
        hazard_raw = self._hazard_backend.infer(image, confidence_threshold)
        return person_raw + hazard_raw


def create_multi_model_detector(
    person_model_path: str | Path,
    hazard_model_path: str | Path,
    model_versions_path: str | Path,
    confidence_threshold: float,
) -> Detector:
    """Factory used by the integration pipeline (Phase 14) when running
    two real models — a person detector and a fire/smoke detector — behind
    one Detector. `Detector`, `ModelClassConfig`, `UltralyticsBackend`, and
    `create_default_detector` are all unchanged; this only adds a second
    backend option that satisfies the same YoloBackend interface."""
    return Detector(
        backend=MultiModelBackend(
            person_backend=UltralyticsBackend(person_model_path),
            hazard_backend=UltralyticsBackend(hazard_model_path),
        ),
        class_config=ModelClassConfig.from_file(model_versions_path),
        confidence_threshold=confidence_threshold,
    )
