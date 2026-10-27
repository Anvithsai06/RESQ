import type { CameraInfo } from "../types/camera";

interface Props {
  cameras: CameraInfo[];
  selected: string;
  onSelect: (cameraId: string) => void;
}

/**
 * Only ever rendered when there's more than one camera (see ScenePanel) —
 * with today's single real camera, the UI shows no switcher at all rather
 * than a disabled or single-option control.
 */
export default function CameraSwitcher({ cameras, selected, onSelect }: Props) {
  return (
    <div className="flex items-center gap-1 rounded-md border border-slate-700 bg-slate-800/60 p-0.5">
      {cameras.map((camera) => {
        const active = camera.camera_id === selected;
        return (
          <button
            key={camera.camera_id}
            type="button"
            onClick={() => onSelect(camera.camera_id)}
            className={`relative rounded px-2.5 py-1 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
              active ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:text-slate-200"
            }`}
            aria-pressed={active}
            title={camera.source_available ? camera.name : `${camera.name} — no video configured`}
          >
            {camera.camera_id}
            {!camera.source_available && (
              <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-slate-600" aria-label="no video" />
            )}
          </button>
        );
      })}
    </div>
  );
}
