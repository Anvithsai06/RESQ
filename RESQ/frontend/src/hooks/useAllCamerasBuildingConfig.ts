import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import type { CameraInfo } from "../types/camera";
import type { ExitConfig, ExitsResponse, ZoneConfig, ZonesResponse } from "../types/building";

export interface CameraBuildingConfig {
  camera: CameraInfo;
  zones: ZoneConfig[];
  exits: ExitConfig[];
  imageWidth: number;
  imageHeight: number;
}

const LAST_RESORT_WIDTH = 720;
const LAST_RESORT_HEIGHT = 1280;

/**
 * Fetches every configured camera's own zones/exits/coordinate-space, for
 * the whole-building overview (Task 4.2) — reuses building/building.json,
 * zones.json and exits.json as the single source of truth via the same
 * per-camera config routes the single-camera view already uses, just
 * fetched for every camera instead of one.
 */
export function useAllCamerasBuildingConfig(cameras: CameraInfo[]) {
  const [configs, setConfigs] = useState<CameraBuildingConfig[]>([]);
  const [loading, setLoading] = useState(true);

  const cameraIds = cameras.map((c) => c.camera_id).join(",");

  // Reset/adjust state during render based on cameras.
  const [prevIds, setPrevIds] = useState(cameraIds);
  if (cameraIds !== prevIds) {
    setPrevIds(cameraIds);
    if (cameras.length === 0) {
      setConfigs([]);
      setLoading(false);
    } else {
      setLoading(true);
    }
  }

  useEffect(() => {
    if (cameras.length === 0) return;
    let cancelled = false;

    Promise.all(
      cameras.map(async (camera) => {
        try {
          const [zonesRes, exitsRes] = await Promise.all([
            fetch(`${API_BASE}/config/cameras/${camera.camera_id}/zones`),
            fetch(`${API_BASE}/config/cameras/${camera.camera_id}/exits`),
          ]);
          const zonesData: ZonesResponse = zonesRes.ok ? await zonesRes.json() : { camera_id: camera.camera_id, zones: [] };
          const exitsData: ExitsResponse = exitsRes.ok ? await exitsRes.json() : { camera_id: camera.camera_id, exits: [] };
          const space = zonesData.coordinate_space ?? exitsData.coordinate_space;
          const imageWidth = space?.width ?? camera.resolution?.[0] ?? LAST_RESORT_WIDTH;
          const imageHeight = space?.height ?? camera.resolution?.[1] ?? LAST_RESORT_HEIGHT;
          return {
            camera,
            zones: zonesData.zones ?? [],
            exits: exitsData.exits ?? [],
            imageWidth,
            imageHeight,
          };
        } catch {
          return { camera, zones: [], exits: [], imageWidth: LAST_RESORT_WIDTH, imageHeight: LAST_RESORT_HEIGHT };
        }
      }),
    ).then((results) => {
      if (!cancelled) {
        setConfigs(results);
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraIds]);

  return { configs, loading };
}
