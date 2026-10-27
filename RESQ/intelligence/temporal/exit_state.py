"""
Exit state machine — WORKFLOW.md Phase 9.

Only configured, trusted exits are ever evaluated — enforced upstream by
vision/zones/engine.py's ZoneEngine, which drops untrusted exits before
this stage ever sees them. An unconfigured door is never classified as an
emergency exit.

    CLEAR ──> OCCUPIED ──(persistent evidence)──> OBSTRUCTED

    weak/missing evidence, at any occupancy ──> UNCERTAIN

Turns Phase 7's raw per-exit signal (occupancy, persistence_seconds) into
this state machine. "Evidence" here is the confidence of whichever tracks
currently occupy the exit polygon — the weakest (minimum) confidence among
them, since one unreliable detection is enough to make the whole read
untrustworthy. A sustained low-confidence read is reported as UNCERTAIN,
never upgraded to OBSTRUCTED, so RESQ never asserts more certainty than the
underlying detections support.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ExitState(str, Enum):
    CLEAR = "CLEAR"
    OCCUPIED = "OCCUPIED"
    OBSTRUCTED = "OBSTRUCTED"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class ExitStateResult:
    exit_id: str
    state: ExitState
    occupancy: int
    persistence_seconds: float
    evidence_confidence: float | None  # None when occupancy == 0 (no evidence needed)


class ExitStateEngine:
    """Turns Phase 7's raw exit occupancy/persistence signal into the
    CLEAR/OCCUPIED/OBSTRUCTED/UNCERTAIN state machine."""

    def __init__(
        self,
        default_persistence_seconds: float = 5.0,
        per_exit_persistence_seconds: dict[str, float] | None = None,
        evidence_min_confidence: float = 0.5,
    ):
        self.default_persistence_seconds = default_persistence_seconds
        self.per_exit_persistence_seconds = per_exit_persistence_seconds or {}
        self.evidence_min_confidence = evidence_min_confidence

    @classmethod
    def from_config_files(cls, thresholds_path: str | Path, exits_path: str | Path) -> "ExitStateEngine":
        with open(thresholds_path) as f:
            thresholds = json.load(f)
        with open(exits_path) as f:
            exits_config = json.load(f)

        per_exit = {
            e["id"]: e["obstruction_persistence_seconds"]
            for e in exits_config["exits"]
            if "obstruction_persistence_seconds" in e
        }
        return cls(
            default_persistence_seconds=thresholds.get("exit_obstruction_persistence_seconds", 5.0),
            per_exit_persistence_seconds=per_exit,
            evidence_min_confidence=thresholds.get("exit_evidence_min_confidence", 0.5),
        )

    def _persistence_threshold(self, exit_id: str) -> float:
        return self.per_exit_persistence_seconds.get(exit_id, self.default_persistence_seconds)

    def update(
        self, temporal_exits: dict, tracks: list, track_exit: dict[int, str | None]
    ) -> dict[str, ExitStateResult]:
        """`temporal_exits` is Phase 7's TemporalSceneState.exits.
        `tracks` is this tick's Track list. `track_exit` is
        vision.zones.engine.ZoneState.track_exit (track_id -> exit_id)."""
        confidences_by_exit: dict[str, list[float]] = {}
        for track in tracks:
            exit_id = track_exit.get(track.track_id)
            if exit_id is not None:
                confidences_by_exit.setdefault(exit_id, []).append(track.confidence)

        results: dict[str, ExitStateResult] = {}
        for exit_id, temporal in temporal_exits.items():
            if temporal.occupancy == 0:
                results[exit_id] = ExitStateResult(
                    exit_id=exit_id,
                    state=ExitState.CLEAR,
                    occupancy=0,
                    persistence_seconds=0.0,
                    evidence_confidence=None,
                )
                continue

            confidences = confidences_by_exit.get(exit_id, [])
            evidence_confidence = min(confidences) if confidences else 0.0

            if evidence_confidence < self.evidence_min_confidence:
                state = ExitState.UNCERTAIN
            elif temporal.persistence_seconds >= self._persistence_threshold(exit_id):
                state = ExitState.OBSTRUCTED
            else:
                state = ExitState.OCCUPIED

            results[exit_id] = ExitStateResult(
                exit_id=exit_id,
                state=state,
                occupancy=temporal.occupancy,
                persistence_seconds=temporal.persistence_seconds,
                evidence_confidence=evidence_confidence,
            )
        return results
