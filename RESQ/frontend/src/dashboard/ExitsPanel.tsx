import type { IncidentState } from "../types/incident";
import type { ExitConfig } from "../types/building";
import Panel, { EmptyState } from "../components/Panel";
import { exitStateStyles } from "../lib/theme";

interface Props {
  incident: IncidentState | null;
  exits: ExitConfig[];
}

/** Exit accessibility. Only configured, trusted exits are ever evaluated. */
export default function ExitsPanel({ incident, exits }: Props) {
  const labelById = new Map(exits.map((e) => [e.id, e.label]));
  const rows = incident?.exits ?? [];

  return (
    <Panel title="Exits" subtitle="Configured emergency exits only" bodyClassName="p-0">
      {rows.length === 0 ? (
        <EmptyState message="No exit data yet." />
      ) : (
        <ul className="divide-y divide-slate-800">
          {rows.map((exit) => {
            const s = exitStateStyles[exit.state];
            return (
              <li key={exit.exit_id} className="flex items-center gap-3 px-4 py-2.5">
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded border text-xs font-semibold ${s.border} ${s.bg} ${s.text}`}
                  aria-hidden
                >
                  {s.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-200">
                    {labelById.get(exit.exit_id) ?? exit.exit_id}
                  </p>
                  <p className="truncate text-xs text-slate-500">
                    {exit.exit_id}
                    {exit.state !== "CLEAR" && exit.occupancy > 0 && (
                      <> · {exit.occupancy} {exit.occupancy === 1 ? "person" : "people"}</>
                    )}
                    {exit.persistence_seconds > 0 && <> · {Math.round(exit.persistence_seconds)}s</>}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded border px-2 py-0.5 text-2xs font-medium ${s.border} ${s.bg} ${s.text}`}
                >
                  {s.label}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {rows.some((e) => e.state === "UNCERTAIN") && (
        <p className="border-t border-slate-800 px-4 py-2.5 text-2xs leading-relaxed text-slate-500">
          "Unclear" means the visual evidence is too weak to judge — not that the exit is usable.
          Verify directly.
        </p>
      )}
    </Panel>
  );
}
