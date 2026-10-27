// Mirrors building/zones.json and building/exits.json — served read-only
// via backend/api/config.py so the situational view can draw real,
// human-curated polygons instead of anything inferred.

export type ZoneType = "danger" | "obstruction" | "safe_observation";

/**
 * The image-space the polygons are expressed in. Declared in config rather
 * than assumed, because polygons are camera-pixel coordinates and are never
 * rescaled at runtime.
 */
export interface CoordinateSpace {
  width: number;
  height: number;
  notes?: string;
}

export interface ZoneConfig {
  id: string;
  type: ZoneType;
  label: string;
  polygon: [number, number][];
}

export interface ZonesResponse {
  camera_id: string;
  coordinate_space?: CoordinateSpace;
  zones: ZoneConfig[];
}

export interface ExitConfig {
  id: string;
  label: string;
  polygon: [number, number][];
  obstruction_persistence_seconds: number;
  trusted: boolean;
}

export interface ExitsResponse {
  camera_id: string;
  coordinate_space?: CoordinateSpace;
  exits: ExitConfig[];
}
