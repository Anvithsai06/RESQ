"""
Priority engine — WORKFLOW.md Phase 10.

    Priority = 0.40 × Hazard Exposure
             + 0.25 × People in Danger Zones
             + 0.20 × Congestion
             + 0.15 × Exit Obstruction

Each component is normalized to 0-100 before weighting, so the final
priority is already in 0-100. Every component score, plus the overall
`confidence` and `uncertainty` flag, is derived only from signals produced
by earlier phases (zone occupancy, temporal hazard/exit state, exit
evidence confidence, and real tracked bounding boxes) — nothing here
infers a fact the CV pipeline didn't actually observe (e.g. no per-object
material classification; flammability is a human-curated zone property,
read from config, never guessed from pixels).

`confidence` is the average evidence-confidence across whatever signals
actually contributed to the score this tick (hazard detection confidence,
exit evidence confidence, average confidence of currently-tracked people).
An empty scene — nothing detected anywhere — defaults to confidence 1.0:
there is no ambiguous evidence to be uncertain about.

`uncertainty` is set whenever the score's supporting evidence is inherently
shaky: low overall confidence, any exit read as UNCERTAIN, or a hazard
that is not (yet) a validated class actually driving the score. Downstream
consumers (Incident State, notification payloads) must surface this flag
rather than presenting a bare number.

Hazard exposure risk factors (both bounded, both optional/config-gated —
zero weight reproduces the original score exactly):

  Zone risk — a hazard tracked inside a more flammable zone, or inside a
  zone that currently has people in it, scores higher than an identical
  hazard (same confidence/persistence) in an empty, low-fuel zone.
  `flammability` per zone comes from building/zones.json (human-curated,
  0-1) — this is metadata about the zone, not a claim the CV pipeline
  detected combustible material.
      zone_risk_multiplier = 1 + flammability_weight * flammability
                                + (occupied_zone_bonus if zone occupied else 0)

  Growth trend — over a short rolling window (default 5s), the hazard's
  own tracked bounding-box area is compared to its area at the start of
  the window. A visibly *growing* hazard gets a bounded boost so the score
  reflects a spreading fire before persistence/confidence alone would
  saturate it; a shrinking or stable hazard gets no penalty and no boost
  beyond 1.0 — this term never reduces the base score.
      growth_rate = (area_now - area_at_window_start) / area_at_window_start / elapsed_seconds
      growth_multiplier = 1 + clamp(growth_rate * growth_rate_scale, 0, growth_max_boost)

  Both multipliers apply to the base (confidence × persistence-ratio × 100)
  hazard score, and the final result is always clamped back to 0-100 — the
  multipliers can shift *when* a hazard reaches a given score, never push
  it past the same 0-100 scale every other component uses.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from intelligence.temporal.exit_state import ExitState


@dataclass
class PriorityComponentScores:
    hazard_exposure: float
    people_in_danger_zones: float
    congestion: float
    exit_obstruction: float


@dataclass
class PriorityResult:
    timestamp: float
    camera_id: str
    priority: float  # 0-100
    band: str  # "normal" | "moderate" | "high" | "critical"
    components: PriorityComponentScores
    contributors: list[str]  # component names with score > 0, weighted-contribution descending
    confidence: float  # 0-1
    uncertainty: bool


class PriorityEngine:
    def __init__(
        self,
        weights: dict[str, float],
        bands: dict[str, float],
        danger_zone_occupancy_saturation: float,
        congestion_high_occupancy: float,
        hazard_persistence_frames: float,
        exit_obstruction_component_scores: dict[str, float],
        uncertainty_min_confidence: float,
        validated_hazard_classes: set[str],
        zone_flammability: dict[str, float] | None = None,
        default_flammability: float = 0.3,
        flammability_weight: float = 0.0,
        occupied_zone_bonus: float = 0.0,
        growth_window_seconds: float = 5.0,
        growth_rate_scale: float = 1.0,
        growth_max_boost: float = 0.0,
    ):
        self.weights = weights
        self.bands = bands
        self.danger_zone_occupancy_saturation = danger_zone_occupancy_saturation
        self.congestion_high_occupancy = congestion_high_occupancy
        self.hazard_persistence_frames = hazard_persistence_frames
        self.exit_obstruction_component_scores = exit_obstruction_component_scores
        self.uncertainty_min_confidence = uncertainty_min_confidence
        self.validated_hazard_classes = validated_hazard_classes

        self.zone_flammability = zone_flammability or {}
        self.default_flammability = default_flammability
        self.flammability_weight = flammability_weight
        self.occupied_zone_bonus = occupied_zone_bonus

        self.growth_window_seconds = growth_window_seconds
        self.growth_rate_scale = growth_rate_scale
        self.growth_max_boost = growth_max_boost
        # class_name -> [(timestamp, bbox_area), ...], oldest first, pruned to
        # growth_window_seconds every tick. Per-engine-instance (per camera).
        self._hazard_area_history: dict[str, list[tuple[float, float]]] = {}

    @classmethod
    def from_config_files(
        cls,
        thresholds_path: str | Path,
        model_versions_path: str | Path,
        zones_path: str | Path | None = None,
    ) -> "PriorityEngine":
        with open(thresholds_path) as f:
            thresholds = json.load(f)
        with open(model_versions_path) as f:
            model_versions = json.load(f)

        norm = thresholds["priority_normalization"]
        hazard_risk = norm.get("hazard_risk", {})

        zone_flammability: dict[str, float] = {}
        if zones_path is not None:
            with open(zones_path) as f:
                zones_config = json.load(f)
            zone_flammability = {
                z["id"]: z["flammability"] for z in zones_config["zones"] if "flammability" in z
            }

        return cls(
            weights=thresholds["priority_weights"],
            bands=thresholds["priority_bands"],
            danger_zone_occupancy_saturation=norm["danger_zone_occupancy_saturation"],
            congestion_high_occupancy=thresholds["congestion"]["high_occupancy"],
            hazard_persistence_frames=thresholds["hazard_persistence_frames"],
            exit_obstruction_component_scores=norm["exit_obstruction_component_scores"],
            uncertainty_min_confidence=norm["uncertainty_min_confidence"],
            validated_hazard_classes=set(model_versions["detector"].get("validated_classes", [])),
            zone_flammability=zone_flammability,
            default_flammability=hazard_risk.get("default_flammability", 0.3),
            flammability_weight=hazard_risk.get("flammability_weight", 0.0),
            occupied_zone_bonus=hazard_risk.get("occupied_zone_bonus", 0.0),
            growth_window_seconds=hazard_risk.get("growth_window_seconds", 5.0),
            growth_rate_scale=hazard_risk.get("growth_rate_scale", 1.0),
            growth_max_boost=hazard_risk.get("growth_max_boost", 0.0),
        )

    def _zone_risk_multiplier(self, class_name: str, tracks: list, zone_state) -> float:
        """Highest-risk zone context among this tick's tracks of this hazard
        class. Returns 1.0 (no boost) if the hazard isn't inside any
        configured zone, or if flammability/occupancy weighting is off."""
        best = 1.0
        for t in tracks:
            if t.class_name != class_name:
                continue
            zone_id = zone_state.track_zone.get(t.track_id)
            if zone_id is None:
                continue
            flammability = self.zone_flammability.get(zone_id, self.default_flammability)
            occupied = zone_state.zone_occupancy.get(zone_id, 0) > 0
            multiplier = 1.0 + self.flammability_weight * flammability
            if occupied:
                multiplier += self.occupied_zone_bonus
            best = max(best, multiplier)
        return best

    def _growth_multiplier(self, class_name: str, tracks: list, timestamp: float) -> float:
        """Bounded boost for a hazard whose tracked bbox area is visibly
        growing within the rolling window — never reduces the score."""
        areas = []
        for t in tracks:
            if t.class_name != class_name:
                continue
            x1, y1, x2, y2 = t.bbox
            areas.append(max(0.0, x2 - x1) * max(0.0, y2 - y1))
        current_area = max(areas) if areas else None

        history = self._hazard_area_history.setdefault(class_name, [])
        if current_area is not None and current_area > 0:
            history.append((timestamp, current_area))
        cutoff = timestamp - self.growth_window_seconds
        while history and history[0][0] < cutoff:
            history.pop(0)

        if current_area is None or len(history) < 2:
            return 1.0  # not enough evidence within the window to claim a trend

        first_t, first_area = history[0]
        elapsed = timestamp - first_t
        if elapsed <= 0 or first_area <= 0:
            return 1.0

        growth_rate = (current_area - first_area) / first_area / elapsed
        boost = max(0.0, min(self.growth_max_boost, growth_rate * self.growth_rate_scale))
        return 1.0 + boost

    def _hazard_exposure(self, temporal_state, tracks: list, zone_state, timestamp: float) -> tuple[float, list[float], bool]:
        best_score = 0.0
        confidences: list[float] = []
        has_unvalidated_contributor = False
        for hazard in temporal_state.hazards.values():
            if not hazard.presence:
                continue
            persistence_ratio = min(1.0, hazard.persistence_frames / self.hazard_persistence_frames)
            base_score = hazard.confidence * persistence_ratio * 100.0

            zone_multiplier = self._zone_risk_multiplier(hazard.class_name, tracks, zone_state)
            growth_multiplier = self._growth_multiplier(hazard.class_name, tracks, timestamp)
            score = min(100.0, base_score * zone_multiplier * growth_multiplier)

            confidences.append(hazard.confidence)
            if score > best_score:
                best_score = score
            if score > 0 and hazard.class_name not in self.validated_hazard_classes:
                has_unvalidated_contributor = True
        return best_score, confidences, has_unvalidated_contributor

    def _people_in_danger_zones(self, danger_zone_occupancy: int) -> float:
        return min(1.0, danger_zone_occupancy / self.danger_zone_occupancy_saturation) * 100.0

    def _congestion(self, temporal_state) -> float:
        max_occupancy = max((z.occupancy for z in temporal_state.zones.values()), default=0)
        return min(1.0, max_occupancy / self.congestion_high_occupancy) * 100.0

    def _exit_obstruction(self, exit_states: dict) -> tuple[float, list[float], bool]:
        best_score = 0.0
        confidences: list[float] = []
        has_uncertain = False
        for result in exit_states.values():
            score = self.exit_obstruction_component_scores[result.state.value]
            if result.evidence_confidence is not None:
                confidences.append(result.evidence_confidence)
            if result.state == ExitState.UNCERTAIN:
                has_uncertain = True
            if score > best_score:
                best_score = score
        return best_score, confidences, has_uncertain

    def _band(self, priority: float) -> str:
        if priority >= self.bands["critical"]:
            return "critical"
        if priority >= self.bands["high"]:
            return "high"
        if priority >= self.bands["moderate"]:
            return "moderate"
        return "normal"

    def update(self, zone_state, temporal_state, exit_states: dict, tracks: list, timestamp: float) -> PriorityResult:
        """
        zone_state: vision.zones.engine.ZoneState (this tick)
        temporal_state: intelligence.temporal.engine.TemporalSceneState (this tick)
        exit_states: dict[str, intelligence.temporal.exit_state.ExitStateResult] (this tick)
        tracks: this tick's vision.tracking.byte_tracker.Track list — includes
                hazard tracks (ByteTrack is class-agnostic), used here for
                zone-risk and growth-rate context.
        """
        hazard_score, hazard_confidences, has_unvalidated_hazard = self._hazard_exposure(
            temporal_state, tracks, zone_state, timestamp
        )
        danger_score = self._people_in_danger_zones(zone_state.danger_zone_occupancy)
        congestion_score = self._congestion(temporal_state)
        exit_score, exit_confidences, has_uncertain_exit = self._exit_obstruction(exit_states)

        components = PriorityComponentScores(
            hazard_exposure=hazard_score,
            people_in_danger_zones=danger_score,
            congestion=congestion_score,
            exit_obstruction=exit_score,
        )

        weighted = {
            "hazard_exposure": self.weights["hazard_exposure"] * hazard_score,
            "people_in_danger_zones": self.weights["people_in_danger_zones"] * danger_score,
            "congestion": self.weights["congestion"] * congestion_score,
            "exit_obstruction": self.weights["exit_obstruction"] * exit_score,
        }
        priority = sum(weighted.values())

        contributors = [name for name, value in weighted.items() if value > 0]
        contributors.sort(key=lambda name: weighted[name], reverse=True)

        track_confidences = [t.confidence for t in tracks]
        all_confidences = hazard_confidences + exit_confidences + track_confidences
        confidence = (sum(all_confidences) / len(all_confidences)) if all_confidences else 1.0

        uncertainty = confidence < self.uncertainty_min_confidence or has_uncertain_exit or has_unvalidated_hazard

        return PriorityResult(
            timestamp=timestamp,
            camera_id=zone_state.camera_id,
            priority=priority,
            band=self._band(priority),
            components=components,
            contributors=contributors,
            confidence=confidence,
            uncertainty=uncertainty,
        )
