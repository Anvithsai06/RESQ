import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import type { CameraInfo } from "../types/camera";

interface UseCamerasResult {
  cameras: CameraInfo[];
  loading: boolean;
  error: string | null;
}

/** One-shot fetch — the camera roster is static config, not per-tick data. */
export function useCameras(): UseCamerasResult {
  const [cameras, setCameras] = useState<CameraInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/config/cameras`)
      .then((r) => {
        if (!r.ok) throw new Error(`Backend returned ${r.status}`);
        return r.json();
      })
      .then((data: CameraInfo[]) => {
        if (!cancelled) setCameras(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load cameras");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { cameras, loading, error };
}
