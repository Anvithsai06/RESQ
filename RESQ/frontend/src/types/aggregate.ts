// Mirrors backend/api/incident.py's GET /incident/aggregate.

export interface AggregateCameraSummary {
  camera_id: string;
  priority: number;
  band: string;
  people_count: number;
  hazard_count: number;
  alert_active: boolean;
}

export interface AggregateIncident {
  cameras_reporting: number;
  highest_priority: number | null;
  highest_priority_camera_id: string | null;
  total_people: number;
  combined_hazard_classes: string[];
  any_alert_active: boolean;
  any_uncertainty: boolean;
  cameras: AggregateCameraSummary[];
}
