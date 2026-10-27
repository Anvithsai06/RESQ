import { describe, expect, it } from "vitest";
import {
  centroid,
  clampPitch,
  imageToGround,
  polygonToGround,
  project,
  spreadOffset,
  type Camera,
} from "./scene3d";

describe("imageToGround — per-camera pixel-to-world mapping", () => {
  it("maps the exact image center to the world origin regardless of resolution", () => {
    // Task 4.3: every camera's own resolution must calibrate independently
    // — this must hold whether the camera is 720x1280 or something else.
    for (const [w, h] of [
      [720, 1280],
      [1920, 1080],
      [320, 568],
      [1, 1],
    ] as const) {
      const p = imageToGround(w / 2, h / 2, w, h, 500);
      expect(p.x).toBeCloseTo(0);
      expect(p.z).toBeCloseTo(0);
      expect(p.y).toBe(0);
    }
  });

  it("scales proportionally to planeScale", () => {
    const small = imageToGround(0, 0, 720, 1280, 100);
    const large = imageToGround(0, 0, 720, 1280, 500);
    expect(large.x).toBeCloseTo(small.x * 5);
    expect(large.z).toBeCloseTo(small.z * 5);
  });

  it("uses the longer image dimension so aspect ratio isn't distorted", () => {
    // A portrait (720x1280) and an equally-scaled landscape camera should
    // place a corner at the same normalized distance from center.
    const portraitCorner = imageToGround(720, 0, 720, 1280, 500);
    const landscapeCorner = imageToGround(1280, 0, 1280, 720, 500);
    const dist = (p: { x: number; z: number }) => Math.hypot(p.x, p.z);
    expect(dist(portraitCorner)).toBeCloseTo(dist(landscapeCorner));
  });

  it("two different cameras' own resolutions never need to match to both calibrate correctly", () => {
    // CAM-01 (720x1280) and a hypothetical differently-sized CAM-02 each
    // independently map their own center to the origin — no shared
    // assumption between them.
    const cam01Center = imageToGround(360, 640, 720, 1280, 500);
    const cam02Center = imageToGround(160, 284, 320, 568, 500);
    expect(cam01Center.x).toBeCloseTo(0);
    expect(cam02Center.x).toBeCloseTo(0);
  });
});

describe("polygonToGround", () => {
  it("maps every vertex through imageToGround with the same resolution/scale", () => {
    const polygon: [number, number][] = [
      [0, 0],
      [720, 0],
      [720, 1280],
      [0, 1280],
    ];
    const ground = polygonToGround(polygon, 720, 1280, 500);
    expect(ground).toHaveLength(4);
    expect(ground[0]).toEqual(imageToGround(0, 0, 720, 1280, 500));
    expect(ground[2]).toEqual(imageToGround(720, 1280, 720, 1280, 500));
  });

  it("returns an empty array for an empty polygon", () => {
    expect(polygonToGround([], 720, 1280, 500)).toEqual([]);
  });
});

describe("centroid", () => {
  it("averages a square's corners to its center", () => {
    const c = centroid([
      { x: 0, y: 0, z: 0 },
      { x: 10, y: 0, z: 0 },
      { x: 10, y: 0, z: 10 },
      { x: 0, y: 0, z: 10 },
    ]);
    expect(c).toEqual({ x: 5, y: 0, z: 5 });
  });

  it("returns the origin for an empty list rather than throwing", () => {
    expect(centroid([])).toEqual({ x: 0, y: 0, z: 0 });
  });
});

describe("project", () => {
  const camera: Camera = { yaw: 0, pitch: 0, zoom: 1 };

  it("places the world origin at the exact screen center", () => {
    const p = project({ x: 0, y: 0, z: 0 }, camera, 640, 420);
    expect(p.x).toBe(320);
    expect(p.y).toBe(210);
  });

  it("moving along x shifts screen x but not screen y at zero rotation", () => {
    const p = project({ x: 100, y: 0, z: 0 }, camera, 640, 420);
    expect(p.x).toBeGreaterThan(320);
    expect(p.y).toBe(210);
  });

  it("zoom scales screen displacement proportionally", () => {
    const near = project({ x: 100, y: 0, z: 0 }, { ...camera, zoom: 1 }, 640, 420);
    const far = project({ x: 100, y: 0, z: 0 }, { ...camera, zoom: 2 }, 640, 420);
    expect(far.x - 320).toBeCloseTo((near.x - 320) * 2);
  });
});

describe("clampPitch", () => {
  it("never returns a value at or past the edge-on/overhead limits", () => {
    expect(clampPitch(-10)).toBeGreaterThan(0);
    expect(clampPitch(10)).toBeLessThan(Math.PI / 2);
  });

  it("passes through values already inside the safe range unchanged", () => {
    expect(clampPitch(0.8)).toBeCloseTo(0.8);
  });
});

describe("spreadOffset", () => {
  it("is deterministic for the same track id — a person doesn't jitter between ticks", () => {
    const a = spreadOffset(17, 40);
    const b = spreadOffset(17, 40);
    expect(a).toEqual(b);
  });

  it("different track ids generally land at different offsets", () => {
    const a = spreadOffset(1, 40);
    const b = spreadOffset(2, 40);
    expect(a).not.toEqual(b);
  });

  it("stays within the given radius", () => {
    for (let id = 0; id < 20; id++) {
      const { dx, dz } = spreadOffset(id, 40);
      expect(Math.hypot(dx, dz)).toBeLessThanOrEqual(40);
    }
  });
});
