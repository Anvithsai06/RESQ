/**
 * Minimal 3D projection maths for the situational view.
 *
 * Implemented directly (yaw/pitch rotation + orthographic projection) rather
 * than pulling in a 3D engine: the scene is a handful of ground polygons and
 * markers, so a full WebGL dependency would be far more weight than the job
 * needs, and SVG keeps the view crisp, themeable and text-selectable.
 */

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface Camera {
  /** Rotation around the vertical axis, radians. */
  yaw: number;
  /** Tilt toward the viewer, radians. */
  pitch: number;
  zoom: number;
}

export interface Projected {
  x: number;
  y: number;
  /** Depth for painter's-algorithm sorting — larger is further from viewer. */
  depth: number;
}

/**
 * Projects a world-space point to 2D screen space.
 * World axes: x = east/west, y = up, z = north/south (ground plane is x/z).
 */
export function project(p: Vec3, camera: Camera, width: number, height: number): Projected {
  const cosYaw = Math.cos(camera.yaw);
  const sinYaw = Math.sin(camera.yaw);

  // Rotate about the vertical (y) axis.
  const rx = p.x * cosYaw - p.z * sinYaw;
  const rz = p.x * sinYaw + p.z * cosYaw;

  const cosPitch = Math.cos(camera.pitch);
  const sinPitch = Math.sin(camera.pitch);

  // Tilt: ground recedes upward, height lifts toward the viewer.
  const screenX = rx * camera.zoom;
  const screenY = (rz * cosPitch - p.y * sinPitch) * camera.zoom;

  return {
    x: width / 2 + screenX,
    y: height / 2 + screenY,
    depth: rz * sinPitch + p.y * cosPitch,
  };
}

/**
 * Maps a camera-image pixel coordinate into the 3D ground plane, centred on
 * the origin so rotation feels natural.
 *
 * NOTE: this is a presentational mapping of image space onto a flat plane for
 * situational awareness — it is not a metric reconstruction of the real world
 * and must not be read as true ground distance.
 */
export function imageToGround(
  px: number,
  py: number,
  imageWidth: number,
  imageHeight: number,
  planeScale = 1,
): Vec3 {
  const longest = Math.max(imageWidth, imageHeight);
  return {
    x: ((px - imageWidth / 2) / longest) * planeScale,
    y: 0,
    z: ((py - imageHeight / 2) / longest) * planeScale,
  };
}

export function polygonToGround(
  polygon: [number, number][],
  imageWidth: number,
  imageHeight: number,
  planeScale = 1,
): Vec3[] {
  return polygon.map(([px, py]) => imageToGround(px, py, imageWidth, imageHeight, planeScale));
}

export function centroid(points: Vec3[]): Vec3 {
  if (points.length === 0) return { x: 0, y: 0, z: 0 };
  const sum = points.reduce(
    (acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y, z: acc.z + p.z }),
    { x: 0, y: 0, z: 0 },
  );
  return { x: sum.x / points.length, y: sum.y / points.length, z: sum.z / points.length };
}

export function toPointsAttr(points: Projected[]): string {
  return points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
}

export function clampPitch(pitch: number): number {
  // Keep the ground plane readable — never flip past edge-on or fully overhead.
  return Math.min(Math.PI / 2.2, Math.max(0.15, pitch));
}

/**
 * Deterministic in-zone offset so multiple people in one zone don't stack on
 * a single point. Derived from track id, so a given person stays put between
 * frames instead of jittering around.
 */
export function spreadOffset(trackId: number, radius: number): { dx: number; dz: number } {
  const golden = 2.399963;
  const angle = trackId * golden;
  const r = radius * (0.35 + 0.5 * ((trackId % 5) / 5));
  return { dx: Math.cos(angle) * r, dz: Math.sin(angle) * r };
}
