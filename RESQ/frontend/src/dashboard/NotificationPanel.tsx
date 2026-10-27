import type { IncidentState } from "../types/incident";
import { formatElapsed } from "../lib/theme";

interface Props {
  incident: IncidentState | null;
}

/**
 * Notification status, stated honestly.
 *
 * A dispatched alert is reported as "notified — awaiting confirmation", never
 * as a guarantee of delivery and never as a claim that anyone has been
 * dispatched or has responded.
 */
export default function NotificationPanel({ incident }: Props) {
  const n = incident?.notification;

  let title = "No alert sent";
  let detail = "Conditions have not met the alerting threshold.";
  let tone = "border-slate-800 bg-slate-900/40";
  let accent = "text-slate-400";
  let icon = "○";
  let elevated = false;

  if (n) {
    switch (n.status) {
      case "sent":
        title = `${n.recipient_name ?? "Emergency service"} notified`;
        detail = `Alert dispatched${n.sent_at !== null ? ` at T+${formatElapsed(n.sent_at)}` : ""} — awaiting confirmation. RESQ cannot confirm receipt or that anyone has been dispatched.`;
        tone = "border-red-500/30 bg-red-500/[0.07]";
        accent = "text-red-300";
        icon = "▲";
        elevated = true;
        break;
      case "pending":
        title = "Alert pending";
        detail = n.reason
          ? `${n.reason.charAt(0).toUpperCase()}${n.reason.slice(1)}.`
          : "Condition must persist before an alert is sent.";
        tone = "border-amber-500/30 bg-amber-500/[0.07]";
        accent = "text-amber-300";
        icon = "◐";
        break;
      case "failed":
        title = "Alert failed to send";
        detail = n.reason ?? "The notification provider reported a failure. Contact the service directly.";
        tone = "border-red-500/30 bg-red-500/[0.07]";
        accent = "text-red-300";
        icon = "✕";
        elevated = true;
        break;
      case "suppressed_cooldown":
        title = "Alert suppressed";
        detail = n.reason ?? "An alert was recently sent for this incident.";
        break;
      case "no_recipient_configured":
        title = "No recipient configured";
        detail = n.reason ?? "No emergency contact is configured for the affected areas.";
        tone = "border-amber-500/30 bg-amber-500/[0.07]";
        accent = "text-amber-300";
        icon = "!";
        break;
      case "suppressed_not_persistent":
      default:
        title = "No alert sent";
        detail = n.reason
          ? `${n.reason.charAt(0).toUpperCase()}${n.reason.slice(1)}.`
          : "Conditions have not met the alerting threshold.";
        break;
    }
  }

  return (
    <div className={`rounded-lg border px-4 py-3 ${elevated ? "shadow-raised" : ""} ${tone}`} role="status" aria-live="polite">
      <div className="flex items-start gap-3">
        <span className={`mt-px text-sm ${accent}`} aria-hidden>
          {icon}
        </span>
        <div className="min-w-0">
          <p className={`text-sm font-semibold ${accent}`}>{title}</p>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{detail}</p>
        </div>
      </div>
    </div>
  );
}
