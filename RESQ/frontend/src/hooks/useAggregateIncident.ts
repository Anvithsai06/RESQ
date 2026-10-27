import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import type { AggregateIncident } from "../types/aggregate";

const POLL_INTERVAL_MS = 2000;

interface UseAggregateResult {
  aggregate: AggregateIncident | null;
  loading: boolean;
  error: string | null;
}

export function useAggregateIncident(): UseAggregateResult {
  const [aggregate, setAggregate] = useState<AggregateIncident | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/incident/aggregate`);
        if (!res.ok) throw new Error(`Backend returned ${res.status}`);
        const data = (await res.json()) as AggregateIncident;
        if (!cancelled) {
          setAggregate(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to reach backend");
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
  }, []);

  return { aggregate, loading, error };
}
