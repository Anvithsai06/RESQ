import type { IncidentState, TimelineEvent } from "../types/incident";
import Panel, { EmptyState } from "../components/Panel";
import { formatElapsed } from "../lib/theme";

interface Props {
  incident: IncidentState | null;
}

const eventMeta: Record<string, { glyph: string; color: string }> = {
  zone_enter: { glyph: "→", color: "text-slate-400" },
  zone_exit: { glyph: "←", color: "text-slate-500" },
  exit_state_change: { glyph: "⇄", color: "text-amber-400" },
  hazard_onset: { glyph: "▲", color: "text-red-400" },
  hazard_cleared: { glyph: "▼", color: "text-emerald-400" },
  priority_band_change: { glyph: "◆", color: "text-amber-400" },
};

/** Humanises the engine's event wording without inventing detail. */
function describe(event: TimelineEvent): string {
  if (event.event_type === "hazard_onset") {
    const cls = String(event.payload.class_name ?? "hazard");
    return `${cls.charAt(0).toUpperCase()}${cls.slice(1)} detected in view`;
  }
  if (event.event_type === "hazard_cleared") {
    const cls = String(event.payload.class_name ?? "hazard");
    return `${cls.charAt(0).toUpperCase()}${cls.slice(1)} no longer visible`;
  }
  if (event.event_type === "exit_state_change") {
    const map: Record<string, string> = {
      CLEAR: "clear",
      OCCUPIED: "in use",
      OBSTRUCTED: "blocked",
      UNCERTAIN: "unclear",
    };
    const to = map[String(event.payload.to)] ?? String(event.payload.to).toLowerCase();
    return `${event.payload.exit_id} is now ${to}`;
  }
  if (event.event_type === "priority_band_change") {
    return `Priority moved from ${String(event.payload.from)} to ${String(event.payload.to)}`;
  }
  return event.description;
}

export default function TimelinePanel({ incident }: Props) {
  const timeline = incident?.timeline ?? [];
  const recent = timeline.slice().reverse();

  return (
    <Panel
      title="Event history"
      subtitle={timeline.length > 0 ? `${timeline.length} events this incident` : undefined}
      bodyClassName="p-0"
    >
      {recent.length === 0 ? (
        <EmptyState message="No events recorded yet." />
      ) : (
        <ol className="max-h-[260px] divide-y divide-slate-800/70 overflow-y-auto">
          {recent.map((event, i) => {
            const meta = eventMeta[event.event_type] ?? { glyph: "•", color: "text-slate-500" };
            return (
              <li
                key={`${event.timestamp}-${event.event_type}-${i}`}
                className="flex items-start gap-3 px-4 py-2"
              >
                <span className="w-11 shrink-0 pt-px font-mono text-2xs tabular-nums text-slate-600">
                  {formatElapsed(event.timestamp)}
                </span>
                <span className={`shrink-0 pt-px text-2xs ${meta.color}`} aria-hidden>
                  {meta.glyph}
                </span>
                <span className="min-w-0 text-sm leading-relaxed text-slate-300">
                  {describe(event)}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
