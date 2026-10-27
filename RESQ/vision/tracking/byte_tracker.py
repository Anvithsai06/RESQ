"""
Tracking — WORKFLOW.md Phase 4.

Gives detected people (and hazards) persistent identities across frames:

    YOLO detections → ByteTrack → Track IDs

Implements ByteTrack's defining idea — a two-stage association that also
matches *low*-confidence detections against still-tracked boxes instead of
discarding them, so a person isn't lost every time a single frame's
confidence dips — on top of a constant-velocity Kalman filter (see
kalman_filter.py) for motion prediction and IoU-based matching (see
matching.py).

Config (configs/bytetrack.yaml):
    track_high_thresh   — confidence floor for first-stage detections
    track_low_thresh    — confidence floor for second-stage detections
    new_track_thresh    — confidence floor to spawn a brand-new track
    track_buffer        — frames a track survives unmatched before removal
    match_thresh        — IoU distance threshold for first-stage matching
    fuse_score          — scale IoU by detection confidence before matching
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
import yaml

from vision.tracking.kalman_filter import KalmanFilter
from vision.tracking.matching import iou_batch, linear_assignment

BBox = tuple[float, float, float, float]

# Fixed per the ByteTrack paper — thresholds are max allowed cost (1 - IoU),
# so this requires a *higher* minimum IoU than the default first-stage
# match_thresh, since low-confidence detections are riskier to match loosely.
_SECOND_STAGE_MATCH_THRESH = 0.5


def _tlbr_to_xyah(bbox: BBox) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1
    cx = x1 + w / 2
    cy = y1 + h / 2
    a = w / h if h > 0 else 0.0
    return np.array([cx, cy, a, h], dtype=float)


def _xyah_to_tlbr(xyah: np.ndarray) -> BBox:
    cx, cy, a, h = xyah
    w = a * h
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


class TrackState(str, Enum):
    TRACKED = "tracked"
    LOST = "lost"
    REMOVED = "removed"


class STrack:
    """Internal per-track state — motion model + bookkeeping."""

    _kalman_filter = KalmanFilter()  # stateless; shared across all tracks

    def __init__(self, bbox: BBox, confidence: float, class_name: str, track_id: int, timestamp: float):
        self.track_id = track_id
        self.class_name = class_name
        self.confidence = confidence
        self.state = TrackState.TRACKED
        self.mean, self.covariance = self._kalman_filter.initiate(_tlbr_to_xyah(bbox))
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.time_since_update = 0
        self.trajectory: list[tuple[float, float]] = [self._center(bbox)]

    @property
    def tlbr(self) -> BBox:
        return _xyah_to_tlbr(self.mean[:4])

    def predict(self) -> None:
        self.mean, self.covariance = self._kalman_filter.predict(self.mean, self.covariance)
        self.time_since_update += 1

    def update(self, bbox: BBox, confidence: float, timestamp: float) -> None:
        self.mean, self.covariance = self._kalman_filter.update(self.mean, self.covariance, _tlbr_to_xyah(bbox))
        self.confidence = confidence
        self.last_seen = timestamp
        self.time_since_update = 0
        self.state = TrackState.TRACKED
        self.trajectory.append(self._center(bbox))

    @staticmethod
    def _center(bbox: BBox) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)


@dataclass
class Track:
    """Public tracker output — one currently-visible tracked entity."""

    track_id: int
    class_name: str
    bbox: BBox
    confidence: float
    first_seen: float
    last_seen: float
    trajectory: list[tuple[float, float]]
    camera_id: str
    current_zone: str | None = None  # populated by the zone engine (Phase 6)


@dataclass
class ByteTrackConfig:
    track_high_thresh: float = 0.5
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.6
    track_buffer: int = 30
    match_thresh: float = 0.8
    fuse_score: bool = True

    @classmethod
    def from_file(cls, path: str | Path) -> "ByteTrackConfig":
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        defaults = cls()
        return cls(
            track_high_thresh=raw.get("track_high_thresh", defaults.track_high_thresh),
            track_low_thresh=raw.get("track_low_thresh", defaults.track_low_thresh),
            new_track_thresh=raw.get("new_track_thresh", defaults.new_track_thresh),
            track_buffer=raw.get("track_buffer", defaults.track_buffer),
            match_thresh=raw.get("match_thresh", defaults.match_thresh),
            fuse_score=raw.get("fuse_score", defaults.fuse_score),
        )


class ByteTracker:
    """One tracker instance per camera — holds all track state across
    frames and issues stable track_ids."""

    def __init__(self, config: ByteTrackConfig | None = None, camera_id: str = ""):
        self.config = config or ByteTrackConfig()
        self.camera_id = camera_id
        self._tracked: list[STrack] = []
        self._lost: list[STrack] = []
        self._next_id = 1

    def _new_id(self) -> int:
        track_id = self._next_id
        self._next_id += 1
        return track_id

    def _cost_matrix(
        self, tracks: list[STrack], bboxes: list[BBox], confidences: list[float], fuse_score: bool = False
    ) -> np.ndarray:
        track_boxes = [t.tlbr for t in tracks]
        ious = iou_batch(track_boxes, bboxes)
        if fuse_score and ious.size:
            ious = ious * np.asarray(confidences, dtype=float)[None, :]
        return 1.0 - ious

    def update(self, detections: list, timestamp: float) -> list[Track]:
        """`detections` is a list of vision.detection.detector.Detection
        for a single frame. Returns currently-visible tracks only (tracks
        held during their lost-but-not-yet-removed grace period are not
        surfaced to callers)."""
        high_dets = [d for d in detections if d.confidence >= self.config.track_high_thresh]
        low_dets = [
            d for d in detections
            if self.config.track_low_thresh <= d.confidence < self.config.track_high_thresh
        ]

        pool = self._tracked + self._lost
        for track in pool:
            track.predict()

        # -- Stage 1: match the full pool against high-confidence detections.
        high_bboxes = [d.bbox for d in high_dets]
        high_conf = [d.confidence for d in high_dets]
        cost1 = self._cost_matrix(pool, high_bboxes, high_conf, fuse_score=self.config.fuse_score)
        matches1, unmatched_pool1, unmatched_high = linear_assignment(cost1, thresh=self.config.match_thresh)

        for pool_idx, det_idx in matches1:
            track = pool[pool_idx]
            det = high_dets[det_idx]
            track.update(det.bbox, det.confidence, timestamp)

        # -- Stage 2: still-tracked (not already lost) unmatched tracks get
        # a second chance against low-confidence detections — the core
        # ByteTrack idea of not discarding low-confidence boxes outright.
        stage2_candidates = [pool[i] for i in unmatched_pool1 if pool[i].state == TrackState.TRACKED]
        low_bboxes = [d.bbox for d in low_dets]
        low_conf = [d.confidence for d in low_dets]
        cost2 = self._cost_matrix(stage2_candidates, low_bboxes, low_conf)
        matches2, unmatched_stage2, _unmatched_low = linear_assignment(cost2, thresh=_SECOND_STAGE_MATCH_THRESH)

        for cand_idx, det_idx in matches2:
            track = stage2_candidates[cand_idx]
            det = low_dets[det_idx]
            track.update(det.bbox, det.confidence, timestamp)

        matched_stage2_ids = {id(stage2_candidates[i]) for i, _ in matches2}
        for track in stage2_candidates:
            if id(track) not in matched_stage2_ids:
                track.state = TrackState.LOST

        # Pool members neither in stage 1 nor stage 2 candidates (i.e.
        # already lost coming into this frame, still unmatched) stay lost.
        matched_pool_ids = {id(pool[i]) for i, _ in matches1}
        stage2_ids = {id(t) for t in stage2_candidates}
        for i in unmatched_pool1:
            track = pool[i]
            if id(track) not in matched_pool_ids and id(track) not in stage2_ids:
                track.state = TrackState.LOST

        # -- New tracks from confident, still-unmatched high detections.
        new_tracks: list[STrack] = []
        for det_idx in unmatched_high:
            det = high_dets[det_idx]
            if det.confidence >= self.config.new_track_thresh:
                new_tracks.append(STrack(det.bbox, det.confidence, det.class_name, self._new_id(), timestamp))

        # -- Rebuild pools; drop tracks lost past the buffer window.
        self._tracked = [t for t in pool if t.state == TrackState.TRACKED] + new_tracks
        still_lost = [t for t in pool if t.state == TrackState.LOST and t.time_since_update <= self.config.track_buffer]
        self._lost = still_lost

        return [
            Track(
                track_id=t.track_id,
                class_name=t.class_name,
                bbox=t.tlbr,
                confidence=t.confidence,
                first_seen=t.first_seen,
                last_seen=t.last_seen,
                trajectory=list(t.trajectory),
                camera_id=self.camera_id,
            )
            for t in self._tracked
        ]
