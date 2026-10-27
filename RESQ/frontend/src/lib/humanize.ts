import type { IncidentState, PriorityBand } from "../types/incident";
import type { ZoneConfig } from "../types/building";

/**
 * Turns RESQ's internal telemetry into language a human responder can act on.
 *
 * Every string here is derived from real Incident State values — nothing is
 * invented, and nothing asserts more certainty than the underlying data
 * supports. Where RESQ is unsure, the wording says so ("appears", "unclear")
 * rather than stating a fact.
 */

const CONTRIBUTOR_LABELS: Record<string, string> = {
  hazard_exposure: "Fire / smoke detected",
  people_in_danger_zones: "People inside a danger area",
  congestion: "Crowding in one area",
  exit_obstruction: "Exit access restricted",
};

const CONTRIBUTOR_EXPLANATIONS: Record<string, string> = {
  hazard_exposure: "A hazard is visible in the monitored view and has persisted across frames.",
  people_in_danger_zones: "One or more tracked people are standing inside a configured danger area.",
  congestion: "Occupancy in a single area is above its configured comfortable level.",
  exit_obstruction: "A configured exit is occupied or blocked in the monitored view.",
};

export function contributorLabel(name: string): string {
  return CONTRIBUTOR_LABELS[name] ?? name.replace(/_/g, " ");
}

export function contributorExplanation(name: string): string {
  return CONTRIBUTOR_EXPLANATIONS[name] ?? "";
}

/** "Person 17" reads better to a responder than "track_id=17". */
export function personLabel(trackId: number): string {
  return `Person ${trackId}`;
}

export function bandHeadline(band: PriorityBand): string {
  switch (band) {
    case "critical":
      return "Critical — immediate attention";
    case "high":
      return "High — needs a decision now";
    case "moderate":
      return "Elevated — monitor closely";
    default:
      return "Normal — no action indicated";
  }
}

export function trendSentence(trend: IncidentState["trend"]): string {
  switch (trend) {
    case "deteriorating":
      return "Conditions are getting worse";
    case "improving":
      return "Conditions are improving";
    default:
      return "Conditions are steady";
  }
}

export function confidenceLabel(confidence: number): string {
  if (confidence >= 0.85) return "High confidence";
  if (confidence >= 0.65) return "Moderate confidence";
  return "Low confidence";
}

/**
 * The single most important sentence on the screen: what is happening, in
 * plain words. Built only from what the incident state actually reports.
 */
export function situationSummary(incident: IncidentState | null, zones: ZoneConfig[]): string {
  if (!incident) return "Waiting for scene data.";

  const zoneLabel = (id: string) => zones.find((z) => z.id === id)?.label ?? id;
  const hazardNames = incident.hazards.map((h) => h.class_name);
  const dangerZoneIds = new Set(
    zones.filter((z) => z.type === "danger").map((z) => z.id),
  );
  const peopleInDanger = incident.people.filter(
    (p) => p.current_zone && dangerZoneIds.has(p.current_zone),
  );

  const parts: string[] = [];

  if (hazardNames.length > 0) {
    const names = formatList(hazardNames.map(capitalize));
    parts.push(`${names} detected in the monitored view`);
  }

  if (peopleInDanger.length > 0) {
    const zoneNames = Array.from(
      new Set(peopleInDanger.map((p) => zoneLabel(p.current_zone as string))),
    );
    parts.push(
      `${peopleInDanger.length} ${peopleInDanger.length === 1 ? "person is" : "people are"} inside ${formatList(zoneNames)}`,
    );
  } else if (incident.people.length > 0) {
    parts.push(
      `${incident.people.length} ${incident.people.length === 1 ? "person" : "people"} tracked, none inside a danger area`,
    );
  }

  const blockedExits = incident.exits.filter((e) => e.state === "OBSTRUCTED");
  if (blockedExits.length > 0) {
    parts.push(`${formatList(blockedExits.map((e) => e.exit_id))} appears blocked`);
  }

  if (parts.length === 0) {
    return "No people or hazards currently detected in the monitored view.";
  }
  return `${parts.join(". ")}.`;
}

/**
 * Concrete, decision-oriented lines for the responder. These are
 * observations and suggestions grounded in the data — never commands, and
 * never a claim that a route is guaranteed safe.
 */
export function recommendations(
  incident: IncidentState | null,
  zones: ZoneConfig[],
): { text: string; tone: "urgent" | "advisory" | "neutral" }[] {
  if (!incident) return [];

  const out: { text: string; tone: "urgent" | "advisory" | "neutral" }[] = [];
  const zoneLabel = (id: string) => zones.find((z) => z.id === id)?.label ?? id;
  const dangerZoneIds = new Set(zones.filter((z) => z.type === "danger").map((z) => z.id));

  const peopleInDanger = incident.people.filter(
    (p) => p.current_zone && dangerZoneIds.has(p.current_zone),
  );
  for (const p of peopleInDanger) {
    out.push({
      text: `${personLabel(p.track_id)} is inside ${zoneLabel(p.current_zone as string)}${
        p.dwell_time > 3 ? ` (${Math.round(p.dwell_time)}s)` : ""
      }`,
      tone: "urgent",
    });
  }

  const blocked = incident.exits.filter((e) => e.state === "OBSTRUCTED");
  for (const e of blocked) {
    out.push({ text: `${e.exit_id} appears blocked — avoid routing through it`, tone: "urgent" });
  }

  const clear = incident.exits.filter((e) => e.state === "CLEAR");
  if (clear.length > 0) {
    out.push({
      text: `${formatList(clear.map((e) => e.exit_id))} ${clear.length === 1 ? "appears" : "appear"} clear in the monitored view`,
      tone: "advisory",
    });
  }

  const unclear = incident.exits.filter((e) => e.state === "UNCERTAIN");
  if (unclear.length > 0) {
    out.push({
      text: `${formatList(unclear.map((e) => e.exit_id))} — evidence too weak to judge, verify directly`,
      tone: "advisory",
    });
  }

  if (incident.uncertainty) {
    out.push({
      text: "Some detections are low-confidence or use unvalidated classes — confirm visually before acting",
      tone: "advisory",
    });
  }

  if (out.length === 0) {
    out.push({ text: "No action indicated from the monitored view", tone: "neutral" });
  }
  return out;
}

export function eventDescription(description: string): string {
  return description;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatList(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
