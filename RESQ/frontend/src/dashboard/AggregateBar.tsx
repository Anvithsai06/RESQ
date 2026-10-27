import type { AggregateIncident } from "../types/aggregate";
import { titleCase } from "../lib/theme";

interface Props {
  aggregate: AggregateIncident | null;
  camerasConfigured: number;
}

/** Building-wide status in one line — legible at a glance across every camera. */
export default function AggregateBar({ aggregate, camerasConfigured }: Props) {
  if (!aggregate) return null;

  const parts: string[] = [
    `${camerasConfigured} ${camerasConfigured === 1 ? "camera" : "cameras"} configured`,
    `${aggregate.cameras_reporting} reporting`,
  ];
  if (aggregate.combined_hazard_classes.length > 0) {
    parts.push(`${aggregate.combined_hazard_classes.map(titleCase).join(", ")} detected`);
  }
  parts.push(`${aggregate.total_people} ${aggregate.total_people === 1 ? "person" : "people"} tracked`);
  if (aggregate.highest_priority !== null) {
    parts.push(`highest priority ${Math.round(aggregate.highest_priority)} on ${aggregate.highest_priority_camera_id}`);
  }

  return (
    <div
      className={`mb-5 flex items-center gap-2 rounded-md border px-3 py-2 text-xs ${
        aggregate.any_alert_active
          ? "border-red-500/30 bg-red-500/[0.07] text-red-200 shadow-raised"
          : "border-slate-800 bg-slate-900/40 text-slate-400"
      }`}
    >
      {aggregate.any_alert_active && (
        <span className="shrink-0 text-red-400" aria-hidden>
          ▲
        </span>
      )}
      <span>{parts.join(" · ")}</span>
    </div>
  );
}
