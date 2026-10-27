import type { CongestionLevel, ExitStateValue, PriorityBand } from "../types/incident";
import type { ZoneType } from "../types/building";

/**
 * RESQ visual system — restrained, operational, professional.
 *
 * Colour is used sparingly and always paired with a text label or icon, so
 * state is never communicated by colour alone (accessibility, and the
 * practical reality that responders may be viewing this on poor displays).
 * Saturated red/amber is reserved for genuine danger states only.
 */

export const bandStyles: Record<
  PriorityBand,
  { text: string; bg: string; border: string; dot: string; label: string; bar: string }
> = {
  normal: {
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/25",
    dot: "bg-emerald-400",
    label: "Normal",
    bar: "bg-emerald-500",
  },
  moderate: {
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/25",
    dot: "bg-amber-400",
    label: "Elevated",
    bar: "bg-amber-500",
  },
  high: {
    text: "text-orange-300",
    bg: "bg-orange-500/10",
    border: "border-orange-500/25",
    dot: "bg-orange-400",
    label: "High",
    bar: "bg-orange-500",
  },
  critical: {
    text: "text-red-300",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    dot: "bg-red-400",
    label: "Critical",
    bar: "bg-red-500",
  },
};

export const exitStateStyles: Record<
  ExitStateValue,
  { text: string; bg: string; border: string; label: string; icon: string }
> = {
  CLEAR: {
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    label: "Clear",
    icon: "✓",
  },
  OCCUPIED: {
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
    label: "In use",
    icon: "•",
  },
  OBSTRUCTED: {
    text: "text-red-300",
    bg: "bg-red-500/10",
    border: "border-red-500/25",
    label: "Blocked",
    icon: "✕",
  },
  UNCERTAIN: {
    text: "text-slate-300",
    bg: "bg-slate-500/10",
    border: "border-slate-500/25",
    label: "Unclear",
    icon: "?",
  },
};

export const congestionTextColor: Record<CongestionLevel, string> = {
  low: "text-slate-400",
  moderate: "text-amber-300",
  high: "text-red-300",
};

/** Floor-plan / 3D zone colours — muted fills, legible strokes. */
export const zoneFillColor: Record<ZoneType, string> = {
  danger: "rgba(239, 68, 68, 0.20)",
  obstruction: "rgba(245, 158, 11, 0.18)",
  safe_observation: "rgba(148, 163, 184, 0.14)",
};

export const zoneStrokeColor: Record<ZoneType, string> = {
  danger: "#ef4444",
  obstruction: "#f59e0b",
  safe_observation: "#94a3b8",
};

export const zoneTypeLabel: Record<ZoneType, string> = {
  danger: "Danger area",
  obstruction: "Obstruction",
  safe_observation: "Safe ground",
};

export const exitFillColor: Record<ExitStateValue, string> = {
  CLEAR: "rgba(16, 185, 129, 0.20)",
  OCCUPIED: "rgba(245, 158, 11, 0.22)",
  OBSTRUCTED: "rgba(239, 68, 68, 0.28)",
  UNCERTAIN: "rgba(148, 163, 184, 0.20)",
};

export const exitStrokeColor: Record<ExitStateValue, string> = {
  CLEAR: "#10b981",
  OCCUPIED: "#f59e0b",
  OBSTRUCTED: "#ef4444",
  UNCERTAIN: "#94a3b8",
};

/**
 * Pipeline timestamps are seconds elapsed within the processed video, not a
 * wall clock — render them as elapsed time rather than inventing a time of day.
 */
export function formatElapsed(timestampSeconds: number): string {
  const safe = Number.isFinite(timestampSeconds) ? Math.max(0, timestampSeconds) : 0;
  const minutes = Math.floor(safe / 60);
  const seconds = Math.floor(safe % 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function titleCase(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
