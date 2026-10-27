import type { IncidentState } from "../types/incident";
import type { ZoneConfig } from "../types/building";
import Panel, { EmptyState } from "../components/Panel";
import { personLabel } from "../lib/humanize";

interface Props {
  incident: IncidentState | null;
  zones: ZoneConfig[];
}

/**
 * "Who is at risk" — people sorted so anyone inside a danger area is first.
 * Only real tracked people appear here; hazards are shown separately.
 */
export default function PeopleAtRiskPanel({ incident, zones }: Props) {
  const zoneById = new Map(zones.map((z) => [z.id, z]));
  const people = [...(incident?.people ?? [])].sort((a, b) => {
    const aDanger = a.current_zone && zoneById.get(a.current_zone)?.type === "danger" ? 1 : 0;
    const bDanger = b.current_zone && zoneById.get(b.current_zone)?.type === "danger" ? 1 : 0;
    if (aDanger !== bDanger) return bDanger - aDanger;
    return b.dwell_time - a.dwell_time;
  });

  const inDangerCount = people.filter(
    (p) => p.current_zone && zoneById.get(p.current_zone)?.type === "danger",
  ).length;

  return (
    <Panel
      title="People"
      subtitle={
        people.length === 0
          ? "Nobody currently tracked"
          : `${people.length} tracked · ${inDangerCount} in a danger area`
      }
      bodyClassName="p-0"
    >
      {people.length === 0 ? (
        <EmptyState message="No people detected in the monitored view." />
      ) : (
        <ul className="divide-y divide-slate-800">
          {people.map((person) => {
            const zone = person.current_zone ? zoneById.get(person.current_zone) : undefined;
            const inDanger = zone?.type === "danger";
            return (
              <li key={person.track_id} className="flex items-center gap-3 px-4 py-2.5">
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums ${
                    inDanger
                      ? "border-red-500/40 bg-red-500/10 text-red-300"
                      : "border-slate-700 bg-slate-800 text-slate-300"
                  }`}
                >
                  {person.track_id}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-slate-200">
                      {personLabel(person.track_id)}
                    </span>
                    {inDanger && (
                      <span className="shrink-0 rounded border border-red-500/30 bg-red-500/10 px-1.5 py-px text-2xs font-medium text-red-300">
                        At risk
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-slate-500">
                    {zone ? zone.label : "Outside configured zones"}
                    {person.dwell_time > 0 && ` · ${Math.round(person.dwell_time)}s`}
                    {person.movement_direction &&
                      person.movement_direction !== "stationary" &&
                      ` · moving ${person.movement_direction.replace("-", " ")}`}
                  </p>
                </div>
                <span className="shrink-0 font-mono text-2xs tabular-nums text-slate-500">
                  {Math.round(person.confidence * 100)}%
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
