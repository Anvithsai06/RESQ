import type { IncidentState } from "../types/incident";
import type { ZoneConfig } from "../types/building";
import Panel, { EmptyState } from "../components/Panel";
import { contributorExplanation, contributorLabel, recommendations } from "../lib/humanize";

interface Props {
  incident: IncidentState | null;
  zones: ZoneConfig[];
}

const toneStyles = {
  urgent: { dot: "bg-red-400", text: "text-slate-200" },
  advisory: { dot: "bg-amber-400", text: "text-slate-300" },
  neutral: { dot: "bg-slate-600", text: "text-slate-400" },
} as const;

/**
 * "Why does it matter" and "what should responders do" in one place: the
 * ranked drivers of the score, then plain-language observations.
 */
export default function AssessmentPanel({ incident, zones }: Props) {
  const contributors = incident?.contributors ?? [];
  const actions = recommendations(incident, zones);

  return (
    <Panel title="Assessment" subtitle="What is driving this score, and what it means">
      <div className="space-y-5">
        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Contributing factors
          </h3>
          {contributors.length === 0 ? (
            <EmptyState message="Nothing is currently elevating the priority score." />
          ) : (
            <ol className="space-y-1.5">
              {contributors.map((name, i) => (
                <li key={name} className="flex items-start gap-2.5">
                  <span className="mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded bg-slate-800 font-mono text-2xs text-slate-400">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-200">
                      {contributorLabel(name)}
                    </p>
                    <p className="text-xs leading-relaxed text-slate-500">
                      {contributorExplanation(name)}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="border-t border-slate-800 pt-4">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Responder notes
          </h3>
          {actions.length === 0 ? (
            <EmptyState message="Waiting for scene data." />
          ) : (
            <ul className="space-y-1.5">
              {actions.map((a, i) => {
                const s = toneStyles[a.tone];
                return (
                  <li key={`${a.text}-${i}`} className="flex items-start gap-2.5">
                    <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${s.dot}`} aria-hidden />
                    <p className={`text-sm leading-relaxed ${s.text}`}>{a.text}</p>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="mt-3 border-t border-slate-800/70 pt-2.5 text-2xs leading-relaxed text-slate-600">
            Decision support only. RESQ does not dispatch responders, guarantee a safe route, or
            assess injuries — a human responder makes the final call.
          </p>
        </div>
      </div>
    </Panel>
  );
}
