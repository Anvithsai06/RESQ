// Mirrors backend/config/cameras.py's CameraConfig, as served by
// GET /config/cameras.

export interface CameraInfo {
  camera_id: string;
  name: string;
  resolution: [number, number] | null;
  source: string;
  zones_config_path: string;
  exits_config_path: string;
  covered_zones: string[];
  covered_exits: string[];
  source_available: boolean;
}
