import type { IncidentState } from "../types/incident";
import type { ZoneConfig } from "../types/building";
import { bandStyles, formatElapsed } from "../lib/theme";
import { bandHeadline, confidenceLabel, situationSummary, trendSentence } from "../lib/humanize";

interface Props {
  incident: IncidentState | null;
  zones: ZoneConfig[];
  connected: boolean;
}

const trendGlyph: Record<IncidentState["trend"], string> = {
  stable: "→",
  deteriorating: "↑",
  improving: "↓",
};

export default function IncidentHeader({ incident, zones, connected }: Props) {
  const band = incident?.band ?? "normal";
  const styles = bandStyles[band];
  const score = incident ? Math.round(incident.priority) : null;

  return (
    <header className="border-b border-slate-800 bg-slate-900/40">
      <div className="mx-auto max-w-[1600px] px-6 py-4">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-slate-700 bg-slate-800 text-base font-bold tracking-tight text-slate-200">
              RQ
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2.5">
                <h1 className="text-lg font-semibold tracking-tight text-slate-100">
                  RESQ
                </h1>
                <span className="hidden text-xs text-slate-500 sm:inline">
                  Emergency Scene Intelligence
                </span>
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-2xs font-medium ${
                    connected
                      ? "border-slate-700 bg-slate-800/60 text-slate-400"
                      : "border-amber-500/30 bg-amber-500/10 text-amber-300"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-400" : "bg-amber-400"}`}
                    aria-hidden
                  />
                  {connected ? "Live" : "Disconnected"}
                </span>
              </div>
              <p className="mt-1 max-w-2xl text-base leading-relaxed text-slate-300">
                {situationSummary(incident, zones)}
              </p>
            </div>
          </div>

          <div className="flex items-stretch gap-3">
            {incident && (
              <div className="flex flex-col justify-center rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-right">
                <span className="text-2xs uppercase tracking-wide text-slate-500">Trend</span>
                <span
                  className={`text-sm font-medium ${
                    incident.trend === "deteriorating"
                      ? "text-red-300"
                      : incident.trend === "improving"
                        ? "text-emerald-300"
                        : "text-slate-300"
                  }`}
                >
                  <span aria-hidden className="mr-1">{trendGlyph[incident.trend]}</span>
                  {trendSentence(incident.trend)}
                </span>
              </div>
            )}

            <div
              className={`min-w-[210px] rounded-md border px-4 py-2.5 shadow-raised ${styles.border} ${styles.bg}`}
              role="status"
              aria-live="polite"
            >
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${styles.dot}`} aria-hidden />
                <span className={`text-sm font-semibold ${styles.text}`}>
                  {bandHeadline(band)}
                </span>
              </div>
              <div className="mt-1.5 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-semibold tabular-nums text-slate-100">
                  {score ?? "—"}
                </span>
                <span className="text-xs text-slate-500">/ 100 priority</span>
              </div>
              <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${styles.bar}`}
                  style={{ width: `${Math.min(100, Math.max(0, score ?? 0))}%` }}
                />
              </div>
              {incident && (
                <div className="mt-2 flex items-center justify-between text-2xs">
                  <span className="text-slate-400">
                    {confidenceLabel(incident.confidence)} · {Math.round(incident.confidence * 100)}%
                  </span>
                  <span className="text-slate-500 tabular-nums">
                    T+{formatElapsed(incident.timestamp)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {incident?.uncertainty && (
          <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-500/25 bg-amber-500/[0.07] px-3 py-2">
            <span className="mt-px text-xs text-amber-400" aria-hidden>⚠</span>
            <p className="text-xs leading-relaxed text-amber-200/90">
              <span className="font-medium">Reduced certainty.</span>{" "}
              Some detections are low-confidence or come from classes not yet validated for this
              deployment. Treat this as decision support and confirm visually — a human makes the
              final call.
            </p>
          </div>
        )}
      </div>
    </header>
  );
}
