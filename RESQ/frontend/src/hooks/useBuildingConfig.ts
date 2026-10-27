import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import type { ExitConfig, ZoneConfig, ZonesResponse, ExitsResponse } from "../types/building";

interface UseBuildingConfigResult {
  zones: ZoneConfig[];
  exits: ExitConfig[];
  /** Image-space the polygons are defined in, from config. */
  imageWidth: number;
  imageHeight: number;
  loading: boolean;
  error: string | null;
}

// Last-resort fallback only — used solely if neither the config response's
// coordinate_space NOR the caller-supplied camera resolution is available.
const LAST_RESORT_WIDTH = 720;
const LAST_RESORT_HEIGHT = 1280;

/**
 * `cameraId` optional: omitted, hits the original unprefixed /config/zones
 * + /config/exits (CAM-01, unchanged behavior). Passed, hits the
 * per-camera routes — each camera's polygons live in its own image space,
 * never assumed to match another camera's.
 *
 * `fallbackResolution` should be that camera's own `resolution` from
 * building/cameras.json (via useCameras()) — used only when the zones/exits
 * response has no explicit coordinate_space block. Never assumes every
 * camera shares one resolution.
 */
export function useBuildingConfig(cameraId?: string, fallbackResolution?: [number, number]): UseBuildingConfigResult {
  const [zones, setZones] = useState<ZoneConfig[]>([]);
  const [exits, setExits] = useState<ExitConfig[]>([]);
  const [imageWidth, setImageWidth] = useState(fallbackResolution?.[0] ?? LAST_RESORT_WIDTH);
  const [imageHeight, setImageHeight] = useState(fallbackResolution?.[1] ?? LAST_RESORT_HEIGHT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Reset state during render when camera ID changes.
  const [prevId, setPrevId] = useState(cameraId);
  if (cameraId !== prevId) {
    setPrevId(cameraId);
    setLoading(true);
    setError(null);
  }

  const resWidth = fallbackResolution?.[0];
  const resHeight = fallbackResolution?.[1];

  useEffect(() => {
    let cancelled = false;

    const zonesUrl = cameraId ? `${API_BASE}/config/cameras/${cameraId}/zones` : `${API_BASE}/config/zones`;
    const exitsUrl = cameraId ? `${API_BASE}/config/cameras/${cameraId}/exits` : `${API_BASE}/config/exits`;

    async function load() {
      try {
        const [zonesRes, exitsRes] = await Promise.all([fetch(zonesUrl), fetch(exitsUrl)]);
        if (!zonesRes.ok || !exitsRes.ok) {
          throw new Error("building configuration could not be loaded");
        }
        const zonesData = (await zonesRes.json()) as ZonesResponse;
        const exitsData = (await exitsRes.json()) as ExitsResponse;
        if (cancelled) return;

        setZones(zonesData.zones ?? []);
        setExits(exitsData.exits ?? []);
        const space = zonesData.coordinate_space ?? exitsData.coordinate_space;
        if (space?.width && space?.height) {
          setImageWidth(space.width);
          setImageHeight(space.height);
        } else if (resWidth && resHeight) {
          setImageWidth(resWidth);
          setImageHeight(resHeight);
        } else {
          setImageWidth(LAST_RESORT_WIDTH);
          setImageHeight(LAST_RESORT_HEIGHT);
        }
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "building configuration could not be loaded");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [cameraId, resWidth, resHeight]);

  return { zones, exits, imageWidth, imageHeight, loading, error };
}
