# CLAUDE.md — Instructions for Claude Code

This file is read automatically by Claude Code at the start of every session
in this repo. It is the source of truth for how to build RESQ. Read
`README.md` and `WORKFLOW.md` before writing any code.

## What RESQ is

RESQ converts emergency video into structured, explainable scene
intelligence for a human responder. It is **not** an autonomous
emergency-response system. It does not dispatch drones/robots, does not
diagnose injuries, does not claim exact real-world distance, and does not
command evacuation routes. It detects → tracks → understands zones →
reasons over time → scores priority → **notifies the nearest configured
government/emergency service** → shows everything on a responder dashboard.
A human always makes the final call.

## Golden rule: one vertical slice first

```
Video → YOLO → ByteTrack → annotated video
```

Get that working before touching zones, temporal state, priority, or
notifications. Do not build every module independently and wire them
together at the end — follow the phase order in `WORKFLOW.md` exactly.

## Locked technology stack (do not change without asking)

| Layer | Choice |
|---|---|
| Frontend | TypeScript + React + Tailwind CSS |
| Backend API | Python + FastAPI |
| AI / CV | Python, OpenCV |
| Detection | YOLO (ultralytics) |
| Tracking | ByteTrack |
| Database | Supabase (PostgreSQL) |
| Realtime | Supabase Realtime |
| Storage | Supabase Storage (floor plans, configs, demo videos) |
| Notifications | Provider-agnostic notifier (`intelligence/notification/`) — mock provider by default, Twilio/SMTP/webhook adapters behind the same interface |

Do not introduce a technology outside this table without it being an
explicit, justified decision recorded in a commit message.

## Repo map

```
resq/
├── frontend/            TypeScript + React dashboard (video, floor plan, timeline)
├── backend/              FastAPI app: routes, services, pydantic schemas, config loading
├── vision/               detection/ (YOLO), tracking/ (ByteTrack), zones/ (polygon engine), video/ (ingestion pipeline)
├── intelligence/         temporal/ (scene-state engine), baseline/ (optional historical baseline),
│                          priority/ (explainable priority score), incident/ (Incident State — the
│                          single object the dashboard consumes), notification/ (government/emergency
│                          service alerting — see below)
├── building/             building.json, cameras.json, zones.json, exits.json, emergency_contacts.json
├── configs/              thresholds.json, model_versions.json, app config
├── models/               YOLO weights (gitignored — do not commit binaries)
├── data/                 demo videos, sample frames (gitignored except tiny fixtures)
├── supabase/migrations/  SQL schema for buildings, cameras, zones, exits, incidents, tracks, events,
│                          baselines, priority_history, notifications
├── tests/                unit/ and integration/
├── docs/                 original PRDs and strategy docs, kept for reference only — not implementation specs
├── README.md
├── WORKFLOW.md           the phase-by-phase build plan — follow it in order
└── .env.example
```

## Build order (see WORKFLOW.md for full detail)

1. Phase 0 — confirm the stack above, do not silently invent alternatives
2. Phase 1 — project skeleton (this repo already has it — extend, don't restructure)
3. Phase 2 — video ingestion
4. Phase 3 — YOLO detection
5. Phase 4 — ByteTrack tracking
6. Phase 5 — building/zone configuration
7. Phase 6 — zone engine (polygon membership, occupancy)
8. Phase 7 — temporal scene-state engine
9. Phase 8 — historical baseline (optional, skip for first stable demo)
10. Phase 9 — exit state machine
11. Phase 10 — priority engine (weighted, explainable, normalized 0–100)
12. Phase 11 — incident state (the bridge object)
13. Phase 12 — **notification engine** (new — see below)
14. Phase 13 — dashboard
15. Phase 14 — integration
16. Phase 15 — demo hardening

Run tests after each phase. Do not skip ahead.

## New requirement: notify the nearest government service

When an incident's priority/state crosses into an emergency condition, RESQ
must notify the nearest configured government/emergency service (police,
fire, ambulance/EMS) for that building automatically, in addition to showing
it on the dashboard.

Design constraints (do not violate these):

- **Config-driven, not autonomous decision-making.** The set of government
  services and their contact channels are defined per building in
  `building/emergency_contacts.json`. RESQ does not look up or guess an
  agency — it notifies whoever is configured as "nearest" for that building.
- **Trigger condition**, defined in `configs/thresholds.json`:
  `priority >= critical_threshold` (default 60 — see WORKFLOW.md §12 for the
  rebalanced priority bands this is tuned against) **and** the condition has
  persisted for `notification_persistence_seconds` (default matches the
  exit-obstruction persistence rule — do not fire on a single noisy frame).
- **One notification per incident escalation**, not one per frame. Use a
  cooldown (`notification_cooldown_seconds`, default 120s) and only re-fire
  if priority drops below the threshold and rises again, or if a new
  distinct hazard/zone contributes.
- **The notification payload must be explainable**, mirroring the Incident
  State: priority score, top contributors, affected zones, exit states,
  confidence, and an explicit "uncertainty" flag if applicable. Never send a
  notification that asserts more certainty than the underlying detections
  support.
- **Provider-agnostic.** Implement `intelligence/notification/notifier.py`
  with a small interface (e.g. `NotificationProvider.send(payload) -> bool`)
  and at least a `MockProvider` (logs + writes to Supabase `notifications`
  table) for the demo. Real providers (Twilio SMS, SMTP email, generic
  webhook) are adapters behind the same interface — wire one in only if
  time permits; the demo must work end-to-end with the mock provider alone.
- **Never block the main pipeline.** Sending a notification must be
  fire-and-forget (async / background task) — a slow or failing notifier
  must not stall detection, tracking, or the dashboard.
- **Log every attempt** (sent, failed, suppressed-by-cooldown) to the
  `notifications` table so the dashboard can show "Nearest emergency
  service notified at HH:MM:SS" or "Notification pending" honestly.
- **Do not** claim the service has "dispatched" anyone, and do not claim
  guaranteed delivery — surface delivery status from the provider as-is.

Add this to the dashboard: a small status line under the priority score,
e.g. `🚨 Fire Dept (Zone 3, 0.4mi) notified at 14:32:07` or
`Notification pending — condition must persist 10s more`.

## Things we do NOT build during the hackathon

- City-wide command centers
- Autonomous dispatch of drones/robots
- Medical triage
- Automatic blueprint generation
- Universal CCTV support
- Guaranteed evacuation routes
- Universal disaster detection
- Uncontrolled/continuous online retraining of the core detector on raw
  daily CCTV (offline, validated updates only)
- Autonomous notification content that overstates certainty — always show
  confidence and uncertainty alongside any alert

## Definition of done

One prerecorded emergency video runs end-to-end with no manual
intervention:

```
VIDEO → DETECTION → TRACKING → ZONE MEMBERSHIP → TEMPORAL EVENTS →
EXIT STATE → PRIORITY → NOTIFICATION → INCIDENT STATE → DASHBOARD
```

The dashboard must answer: WHO? WHAT? WHERE? WHAT CHANGED? IS IT GETTING
WORSE? WHY DOES IT MATTER? HOW CERTAIN ARE WE? WAS ANYONE NOTIFIED?

## Working conventions for Claude Code

- Implement one phase at a time, run relevant tests, then move on.
- Use small, focused commits following the branch/commit conventions in
  `WORKFLOW.md` §19 (add `feature/notification-engine` to that list).
- Never commit model weights, video files, or `.env` — see `.gitignore`.
- Treat `docs/` (the original PRDs) as background/positioning material, not
  as literal schemas to copy — the exact API/schema is an implementation
  decision per `WORKFLOW.md`.
- If something in `docs/` conflicts with `WORKFLOW.md` or this file, this
  file and `WORKFLOW.md` win.
