import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import type { IncidentState } from "../types/incident";
import type { CameraInfo } from "../types/camera";
import Panel from "../components/Panel";
import CameraSwitcher from "./CameraSwitcher";
import UploadControl from "./UploadControl";

interface Props {
  incident: IncidentState | null;
  cameras: CameraInfo[];
  selectedCamera: string;
  onSelectCamera: (cameraId: string) => void;
}

type MediaStatus = { annotated_available: boolean; source_available: boolean };

/**
 * Shows the real camera footage with real detections drawn on it (rendered
 * by scripts/render_annotated_demo.py using the actual models). If that
 * file hasn't been produced, the panel says so plainly and falls back to
 * raw footage — it never substitutes a placeholder clip. When more than
 * one camera is configured, a switcher lets the operator change which
 * feed is shown; with one camera it's invisible, so today's setup renders
 * exactly as before.
 */
export default function ScenePanel({ incident, cameras, selectedCamera, onSelectCamera }: Props) {
  const [status, setStatus] = useState<MediaStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [videoFailed, setVideoFailed] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Reset state during render when camera or refresh key changes.
  const [prevId, setPrevId] = useState(selectedCamera);
  const [prevKey, setPrevKey] = useState(refreshKey);
  if (selectedCamera !== prevId || refreshKey !== prevKey) {
    setPrevId(selectedCamera);
    setPrevKey(refreshKey);
    setStatus(null);
    setVideoFailed(false);
  }

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/media/${selectedCamera}/status`)
      .then((r) => {
        if (!r.ok) throw new Error(`status ${r.status}`);
        return r.json();
      })
      .then((data: MediaStatus) => !cancelled && setStatus(data))
      .catch(() => !cancelled && setError("Scene media unavailable"));
    return () => {
      cancelled = true;
    };
  }, [selectedCamera, refreshKey]);

  const annotated = status?.annotated_available ?? false;
  const source = status?.source_available ?? false;
  const src = annotated
    ? `${API_BASE}/media/${selectedCamera}/annotated`
    : source
      ? `${API_BASE}/media/${selectedCamera}/source`
      : null;

  const peopleCount = incident?.people.length ?? 0;
  const hazards = incident?.hazards ?? [];
  const activeCamera = cameras.find((c) => c.camera_id === selectedCamera);

  return (
    <Panel
      title="Live scene"
      subtitle={annotated ? "Camera view with detections and track IDs" : "Camera view"}
      action={
        <div className="flex items-center gap-2">
          {cameras.length > 1 && (
            <CameraSwitcher cameras={cameras} selected={selectedCamera} onSelect={onSelectCamera} />
          )}
          <UploadControl cameraId={selectedCamera} onReady={() => setRefreshKey((k) => k + 1)} />
          <span className="shrink-0 rounded border border-slate-700 bg-slate-800/60 px-2 py-0.5 font-mono text-2xs text-slate-400">
            {selectedCamera}
          </span>
        </div>
      }
      bodyClassName="flex flex-col"
    >
      <div className="relative flex min-h-[260px] flex-1 items-center justify-center overflow-hidden rounded-md border border-slate-800 bg-slate-950">
        {error || (!src && status) || videoFailed ? (
          <div className="px-6 py-10 text-center">
            <p className="text-sm text-slate-400">
              {videoFailed
                ? "Scene video could not be played"
                : activeCamera && !activeCamera.source_available
                  ? `No video configured for ${selectedCamera} yet`
                  : "No scene video available"}
            </p>
            {(!activeCamera || activeCamera.source_available) && (
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Render it with{" "}
                <code className="rounded bg-slate-800 px-1 py-0.5 font-mono text-2xs text-slate-400">
                  python3 scripts/render_annotated_demo.py
                </code>
              </p>
            )}
          </div>
        ) : !status ? (
          <p className="text-sm text-slate-600">Loading scene…</p>
        ) : (
          <video
            key={src ?? "none"}
            src={src ?? undefined}
            className="max-h-[420px] w-auto max-w-full"
            controls
            autoPlay
            muted
            loop
            playsInline
            onError={() => setVideoFailed(true)}
          />
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="rounded border border-slate-700 bg-slate-800/50 px-2 py-1 text-xs text-slate-300">
          {peopleCount} {peopleCount === 1 ? "person" : "people"} tracked
        </span>
        {hazards.map((h) => (
          <span
            key={h.class_name}
            className="rounded border border-red-500/25 bg-red-500/10 px-2 py-1 text-xs text-red-300"
          >
            {h.class_name === "fire" ? "Fire" : h.class_name === "smoke" ? "Smoke" : h.class_name} ·{" "}
            {Math.round(h.confidence * 100)}%
          </span>
        ))}
        {hazards.length === 0 && incident && (
          <span className="rounded border border-slate-700 bg-slate-800/50 px-2 py-1 text-xs text-slate-400">
            No hazard in view
          </span>
        )}
        {!annotated && source && (
          <span className="ml-auto text-2xs text-slate-600">
            Showing unannotated source footage
          </span>
        )}
      </div>
    </Panel>
  );
}
