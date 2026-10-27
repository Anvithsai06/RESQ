import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import type { IncidentState } from "../types/incident";

const POLL_INTERVAL_MS = 2000;

interface UseIncidentStateResult {
  incident: IncidentState | null;
  loading: boolean;
  error: string | null;
}

// Polls the backend rather than using Supabase Realtime — matches the
// "local + hosted Supabase" deployment decision (Phase 0) without
// requiring Realtime wiring before Phase 14 has a live pipeline to push
// updates. Swapping this for a Realtime subscription later shouldn't
// require touching any component that consumes this hook.
//
// `cameraId` is optional: omitted (or undefined), it hits the original
// single-camera /incident/current route — unchanged behavior for any
// existing single-camera consumer. Passed, it hits the per-camera route.
export function useIncidentState(cameraId?: string): UseIncidentStateResult {
  const [incident, setIncident] = useState<IncidentState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Reset loading state during render when camera ID changes.
  const [prevId, setPrevId] = useState(cameraId);
  if (cameraId !== prevId) {
    setPrevId(cameraId);
    setLoading(true);
  }

  useEffect(() => {
    let cancelled = false;

    const url = cameraId ? `${API_BASE}/incident/camera/${cameraId}` : `${API_BASE}/incident/current`;

    async function poll() {
      try {
        const res = await fetch(url);
        if (res.status === 404) {
          if (!cancelled) {
            setIncident(null);
            setError(null);
          }
          return;
        }
        if (!res.ok) {
          throw new Error(`Backend returned ${res.status}`);
        }
        const data = (await res.json()) as IncidentState;
        if (!cancelled) {
          setIncident(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to reach backend");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    poll();
    const id = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [cameraId]);

  return { incident, loading, error };
}
