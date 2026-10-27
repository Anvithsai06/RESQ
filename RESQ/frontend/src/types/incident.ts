// Mirrors intelligence/incident/state.py's IncidentState (WORKFLOW.md
// Phase 11) — field names match the Python dataclasses exactly, since
// backend/api/incident.py serves them via dataclasses.asdict() as-is.

export type PriorityBand = "normal" | "moderate" | "high" | "critical";
export type Trend = "stable" | "deteriorating" | "improving";
export type ExitStateValue = "CLEAR" | "OCCUPIED" | "OBSTRUCTED" | "UNCERTAIN";
export type CongestionLevel = "low" | "moderate" | "high";

export interface IncidentPerson {
  track_id: number;
  class_name: string;
  current_zone: string | null;
  confidence: number;
  dwell_time: number;
  movement_direction: string | null;
}

export interface IncidentHazard {
  class_name: string;
  presence: boolean;
  confidence: number;
  persistence_frames: number;
}

export interface IncidentExit {
  exit_id: string;
  state: ExitStateValue;
  occupancy: number;
  persistence_seconds: number;
  evidence_confidence: number | null;
}

export interface IncidentZoneCongestion {
  zone_id: string;
  occupancy: number;
  congestion_state: CongestionLevel;
}

export interface TimelineEvent {
  timestamp: number;
  event_type: string;
  description: string;
  payload: Record<string, unknown>;
}

export type NotificationDeliveryStatus =
  | "not_sent"
  | "pending"
  | "sent"
  | "failed"
  | "suppressed_cooldown"
  | "suppressed_not_persistent"
  | "no_recipient_configured";

export interface NotificationStatus {
  status: NotificationDeliveryStatus;
  reason: string | null;
  recipient_name: string | null;
  sent_at: number | null;
}

export interface IncidentState {
  timestamp: number;
  camera_id: string;
  priority: number;
  band: PriorityBand;
  trend: Trend;
  affected_zones: string[];
  people: IncidentPerson[];
  hazards: IncidentHazard[];
  exits: IncidentExit[];
  congestion: Record<string, IncidentZoneCongestion>;
  contributors: string[];
  confidence: number;
  uncertainty: boolean;
  notification: NotificationStatus;
  timeline: TimelineEvent[];
}
