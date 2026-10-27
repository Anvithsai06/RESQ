import { useEffect, useRef } from "react";
import { useCameraUpload } from "../hooks/useCameraUpload";

interface Props {
  cameraId: string;
  onReady?: () => void;
}

const ACCEPTED = ".mp4,.mov,.avi,.mkv,.webm";

/**
 * Lets an operator supply a video for this camera at demo time (Task 3).
 * The uploaded clip goes through the real pipeline — this control only
 * ever reflects genuine progress from the backend, never a canned
 * "done" the instant the file is sent.
 */
export default function UploadControl({ cameraId, onReady }: Props) {
  const { status, detail, ticksProcessed, totalTicks, upload, reset } = useCameraUpload(cameraId);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload(file);
    e.target.value = ""; // allow re-selecting the same file later
  };

  useEffect(() => {
    if (status === "ready") onReady?.();
  }, [status, onReady]);

  if (status === "idle") {
    return (
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="rounded border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        Upload video
        <input ref={inputRef} type="file" accept={ACCEPTED} className="hidden" onChange={handleChange} />
      </button>
    );
  }

  const progressLabel =
    status === "processing" && totalTicks
      ? `Processing frame ${ticksProcessed}/${totalTicks}…`
      : status === "processing"
        ? `Processing… (${ticksProcessed} frames so far)`
        : status === "uploading"
          ? "Uploading…"
          : status === "validating"
            ? "Validating…"
            : status === "ready"
              ? "Ready"
              : "Upload failed";

  const tone =
    status === "failed" ? "border-red-500/30 text-red-300" : status === "ready" ? "border-emerald-500/30 text-emerald-300" : "border-slate-700 text-slate-300";

  return (
    <div className="flex items-center gap-2">
      <span className={`rounded border bg-slate-800/60 px-2.5 py-1 text-xs font-medium ${tone}`} title={detail ?? undefined}>
        {progressLabel}
      </span>
      {(status === "ready" || status === "failed") && (
        <button
          type="button"
          onClick={reset}
          className="rounded border border-slate-700 bg-slate-800/60 px-2 py-1 text-xs text-slate-400 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        >
          Upload another
        </button>
      )}
      {status === "failed" && detail && (
        <span className="max-w-[260px] truncate text-2xs text-red-400" title={detail}>
          {detail}
        </span>
      )}
    </div>
  );
}
