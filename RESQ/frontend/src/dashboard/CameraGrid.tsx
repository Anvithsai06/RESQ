import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import type { CameraInfo } from "../types/camera";
import type { AggregateIncident } from "../types/aggregate";
import { bandStyles } from "../lib/theme";

interface Props {
  cameras: CameraInfo[];
  aggregate: AggregateIncident | null;
  onSelectCamera: (cameraId: string) => void;
}

type MediaStatus = { annotated_available: boolean; source_available: boolean };

/**
 * Every camera as a small tile: live feed (or an honest "no video" state),
 * people/hazard counts, and a priority-band-colored border. Detection
 * itself always runs server-side against the real video at full
 * resolution — this view only ever downscales the *display*, via CSS,
 * never the frames the detectors actually see.
 */
export default function CameraGrid({ cameras, aggregate, onSelectCamera }: Props) {
  const summaryByCameraId = new Map((aggregate?.cameras ?? []).map((c) => [c.camera_id, c]));

  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}
    >
      {cameras.map((camera) => (
        <CameraTile
          key={camera.camera_id}
          camera={camera}
          summary={summaryByCameraId.get(camera.camera_id)}
          onSelect={() => onSelectCamera(camera.camera_id)}
        />
      ))}
    </div>
  );
}

function CameraTile({
  camera,
  summary,
  onSelect,
}: {
  camera: CameraInfo;
  summary: AggregateIncident["cameras"][number] | undefined;
  onSelect: () => void;
}) {
  const [status, setStatus] = useState<MediaStatus | null>(null);
  const [videoFailed, setVideoFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/media/${camera.camera_id}/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: MediaStatus | null) => !cancelled && setStatus(data))
      .catch(() => !cancelled && setStatus(null));
    return () => {
      cancelled = true;
    };
  }, [camera.camera_id]);

  const src = status?.annotated_available
    ? `${API_BASE}/media/${camera.camera_id}/annotated`
    : status?.source_available
      ? `${API_BASE}/media/${camera.camera_id}/source`
      : null;

  const styles = summary ? bandStyles[summary.band as keyof typeof bandStyles] : bandStyles.normal;
  const reporting = summary !== undefined;
  const needsAttention = reporting && summary!.band !== "normal";

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`group flex flex-col overflow-hidden rounded-lg border bg-slate-900/40 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
        reporting ? styles.border : "border-slate-800"
      } ${needsAttention ? "shadow-raised" : "shadow-panel"} hover:border-slate-600`}
    >
      {/* Fixed height rather than aspect-video: source footage can be
          portrait or landscape per camera, and a fixed tile height keeps
          the grid uniform regardless — object-cover fills it either way. */}
      <div className="relative flex h-40 shrink-0 items-center justify-center overflow-hidden bg-slate-950">
        {src && !videoFailed ? (
          <video
            src={src}
            className="h-full w-full object-cover"
            autoPlay
            muted
            loop
            playsInline
            onError={() => setVideoFailed(true)}
          />
        ) : (
          <p className="px-4 text-center text-xs text-slate-600">
            {camera.source_available ? "Video unavailable" : "No video configured"}
          </p>
        )}
        {reporting && (
          <span
            className={`absolute right-2 top-2 rounded px-1.5 py-0.5 text-2xs font-medium ${styles.bg} ${styles.text}`}
          >
            {styles.label}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-200">{camera.name}</p>
          <p className="truncate text-2xs text-slate-500">{camera.camera_id}</p>
        </div>
        {reporting ? (
          <div className="flex shrink-0 items-center gap-2 text-2xs text-slate-400">
            <span>
              {summary!.people_count} {summary!.people_count === 1 ? "person" : "people"}
            </span>
            {summary!.hazard_count > 0 && <span className="text-red-300">{summary!.hazard_count} hazard</span>}
          </div>
        ) : (
          <span className="shrink-0 text-2xs text-slate-600">Not reporting</span>
        )}
      </div>
    </button>
  );
}
