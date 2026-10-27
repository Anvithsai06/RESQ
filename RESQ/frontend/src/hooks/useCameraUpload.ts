import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";

export type UploadStatus = "idle" | "uploading" | "validating" | "processing" | "ready" | "failed";

interface UploadState {
  status: UploadStatus;
  detail: string | null;
  ticksProcessed: number;
  totalTicks: number | null;
}

const POLL_INTERVAL_MS = 1000;

/**
 * Drives Task 3's manual upload flow: POSTs the file, then polls
 * GET /cameras/{camera_id}/upload/status until the real pipeline run
 * reaches "ready" or "failed" — never assumes instant availability.
 */
export function useCameraUpload(cameraId: string) {
  const [state, setState] = useState<UploadState>({
    status: "idle",
    detail: null,
    ticksProcessed: 0,
    totalTicks: null,
  });
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const upload = useCallback(
    async (file: File) => {
      stopPolling();
      setState({ status: "uploading", detail: null, ticksProcessed: 0, totalTicks: null });

      const form = new FormData();
      form.append("file", file);

      try {
        const res = await fetch(`${API_BASE}/cameras/${cameraId}/upload`, { method: "POST", body: form });
        const body = await res.json();
        if (!res.ok) {
          setState({ status: "failed", detail: body.detail ?? "Upload rejected", ticksProcessed: 0, totalTicks: null });
          return;
        }
        setState({ status: "processing", detail: null, ticksProcessed: 0, totalTicks: body.total_ticks ?? null });

        pollRef.current = window.setInterval(async () => {
          try {
            const statusRes = await fetch(`${API_BASE}/cameras/${cameraId}/upload/status`);
            if (!statusRes.ok) return;
            const statusBody = await statusRes.json();
            setState({
              status: statusBody.status,
              detail: statusBody.detail,
              ticksProcessed: statusBody.ticks_processed ?? 0,
              totalTicks: statusBody.total_ticks ?? null,
            });
            if (statusBody.status === "ready" || statusBody.status === "failed") {
              stopPolling();
            }
          } catch {
            // transient network hiccup — keep polling, next tick may succeed
          }
        }, POLL_INTERVAL_MS);
      } catch (err) {
        setState({
          status: "failed",
          detail: err instanceof Error ? err.message : "Upload failed",
          ticksProcessed: 0,
          totalTicks: null,
        });
      }
    },
    [cameraId, stopPolling],
  );

  const reset = useCallback(() => {
    stopPolling();
    setState({ status: "idle", detail: null, ticksProcessed: 0, totalTicks: null });
  }, [stopPolling]);

  return { ...state, upload, reset };
}
