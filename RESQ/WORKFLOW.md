# RESQ — Development Workflow

This document defines the implementation workflow for the RESQ hackathon MVP.

The goal is not to build a giant emergency-management platform.

The goal is to make one vertical slice work end-to-end:

```text
Emergency Video
      ↓
Detection
      ↓
Tracking
      ↓
Zone Understanding
      ↓
Building Context
      ↓
Temporal Scene State
      ↓
Priority
      ↓
Nearest-Service Notification
      ↓
Responder Dashboard
```

---

# 1. Build Strategy

## Rule #1 — Make the vertical slice work first

Do not build every feature independently and connect everything at the end.

The first successful milestone should be:

```text
video.mp4
  ↓
YOLO
  ↓
ByteTrack
  ↓
annotated video
```

Then progressively add intelligence.

---

# 2. Implementation Phases

## Phase 0 — Stack Lock

Before production implementation, the team must explicitly select:

```text
Frontend:      TypeScript + React + Tailwind CSS
Backend:       Python + FastAPI
Database:      Supabase (PostgreSQL)
Video:         Python + OpenCV, prerecorded emergency footage
Deployment:    local / demo host (finalize before Phase 13)
Floor-plan format: image + polygon JSON (see building/zones.json)
Notifications: provider-agnostic notifier, mock provider for the demo
```

Do not silently invent these choices.

The source architecture does not specify deployment target or floor-plan
image format beyond "an implementation choice" — lock those explicitly with
the team before Phase 1.

---

# 3. Phase 1 — Project Skeleton

Create:

```text
resq/
├── frontend/
├── backend/
├── vision/
├── intelligence/
│   ├── temporal/
│   ├── baseline/
│   ├── priority/
│   ├── incident/
│   └── notification/
├── building/
├── configs/
├── models/
├── data/
└── tests/
```

Add:

```text
README.md
WORKFLOW.md
CLAUDE.md
.env.example
.gitignore
```

Create a single configuration source for:

- Building
- Cameras
- Zones
- Exits
- Thresholds
- Model versions
- Emergency contacts (nearest police / fire / EMS per building)

---

# 4. Phase 2 — Video Ingestion

## Goal

Read the selected emergency footage reliably.

Pipeline:

```text
Video
 ↓
Decoder
 ↓
Frame Sampling
 ↓
Timestamp
 ↓
Frame
```

Implement:

- Video opening
- Frame iteration
- FPS detection
- Sampling interval
- Frame dimensions
- Timestamp
- End-of-video handling

## Definition of Done

The system can:

```text
input.mp4
    ↓
frame stream
```

with deterministic timestamps.

---

# 5. Phase 3 — Detection

## Goal

Detect people and validated hazard classes.

Pipeline:

```text
Frame
 ↓
YOLO
 ↓
Detection[]
```

Each detection should contain:

```text
class
confidence
bounding_box
timestamp
camera_id
```

Example:

```json
{
  "class": "person",
  "confidence": 0.94,
  "bbox": [x1, y1, x2, y2],
  "timestamp": 12.53,
  "camera_id": "CAM-01"
}
```

## Definition of Done

The dashboard/video overlay can show:

```text
PERSON 0.94
```

with a bounding box.

---

# 6. Phase 4 — Tracking

## Goal

Give people persistent identities.

Pipeline:

```text
YOLO detections
      ↓
ByteTrack
      ↓
Track IDs
```

Example:

```text
Frame 101 → Person #17
Frame 102 → Person #17
Frame 103 → Person #17
```

Track state should contain:

```text
track_id
class
bbox
confidence
first_seen
last_seen
trajectory
current_zone
```

## Definition of Done

The same visible person keeps a stable ID across consecutive frames in the demo.

---

# 7. Phase 5 — Building Configuration

Create the trusted building model.

Configure:

```text
Building
 ├── Floor
 │   ├── Zones
 │   ├── Exits
 │   └── Connectivity
 │
 └── Cameras
     ├── Position
     ├── Orientation
     └── Covered zones
```

For each camera:

```text
Camera
 ↓
Image-space polygons
 ↓
Building zones
```

Example:

```json
{
  "camera_id": "CAM-01",
  "zones": [
    {
      "id": "DANGER-A",
      "type": "danger",
      "polygon": [[100,100],[500,100],[500,400],[100,400]]
    }
  ]
}
```

Also configure `building/emergency_contacts.json` — the nearest police,
fire, and EMS contact channel(s) for this building. This is a static,
human-curated config, not something RESQ infers at runtime.

The exact schema is an implementation choice.

---

# 8. Phase 6 — Zone Engine

## Goal

Convert tracked people into spatial state.

Pipeline:

```text
Track
 ↓
Point / bounding-box reference
 ↓
Polygon membership
 ↓
Zone
```

Calculate:

- Current zone
- Enter event
- Exit event
- Occupancy
- Danger-zone occupancy
- Exit occupancy

Example:

```text
Person #17
     ↓
DANGER-A
     ↓
INSIDE
```

Then:

```text
people_in_danger += 1
```

---

# 9. Phase 7 — Temporal Scene Engine

This is where RESQ starts becoming more than object detection.

Maintain rolling state.

For each tracked entity:

```text
first_seen
last_seen
current_zone
previous_zone
dwell_time
movement_direction
```

For each zone:

```text
occupancy
occupancy_change
entry_count
exit_count
dwell_distribution
congestion_state
```

For hazards:

```text
presence
confidence
persistence
```

For exits:

```text
occupancy
obstruction
persistence
state
```

---

# 10. Phase 8 — Historical Baseline

Historical baseline is optional for the first stable demo.

If implemented:

```text
Normal Footage
      ↓
Scene Statistics
      ↓
Baseline
      ↓
Current Scene
      ↓
Deviation
```

Track things such as:

- Normal occupancy
- Typical movement
- Typical zone usage
- Time-window behavior

## Important

Do NOT continuously retrain the core detector on raw daily CCTV.

Use daily footage for:

```text
scene statistics
baseline updates
camera health
candidate hard examples
```

Controlled model updates should remain offline and validated.

---

# 11. Phase 9 — Exit State

Only configured exits are evaluated.

State machine:

```text
             ┌───────────┐
             │   CLEAR   │
             └─────┬─────┘
                   │
                   ↓
             ┌───────────┐
             │ OCCUPIED  │
             └─────┬─────┘
                   │ persistent evidence
                   ↓
             ┌───────────┐
             │OBSTRUCTED │
             └───────────┘

Weak / missing evidence
        ↓
     UNCERTAIN
```

Do not classify a random door as an emergency exit.

---

# 12. Phase 10 — Priority Engine

Implement the documented prototype:

```text
Priority =
    0.40 × Hazard Exposure
  + 0.25 × People in Danger Zones
  + 0.20 × Congestion
  + 0.15 × Exit Obstruction
```

Normalize each component to 0–100.

Output:

```json
{
  "priority": 82,
  "contributors": [
    "hazard_exposure",
    "people_in_danger_zone",
    "exit_obstruction"
  ],
  "confidence": 0.87,
  "uncertainty": false
}
```

The exact API/schema is an implementation decision.

### 12.1 Hazard exposure risk factors (added post-hackathon-review)

`Hazard Exposure`'s base score is `confidence × persistence_ratio × 100`
(persistence_ratio = min(1, persistence_frames / hazard_persistence_frames)),
same as originally documented. Two bounded, config-gated multipliers were
added on top — both default to a no-op (multiplier 1.0) unless
`configs/thresholds.json`'s `priority_normalization.hazard_risk` block
enables them, and the result is always clamped back to 0–100:

```text
final_hazard_score = min(100, base_score × zone_risk_multiplier × growth_multiplier)
```

**Zone risk** — a hazard tracked inside a zone reads that zone's
human-curated `flammability` (0–1, from `building/zones.json`, never
inferred from pixels) and whether the zone currently has people in it:

```text
zone_risk_multiplier = 1 + flammability_weight × flammability
                          + (occupied_zone_bonus if zone occupied else 0)
```

**Growth trend** — over a rolling window (`growth_window_seconds`, default
5s), compares the hazard's own tracked bounding-box area now vs. at the
start of the window. Requires at least 2 samples inside the window; a
single observation never claims a trend. Never reduces the score — a
shrinking or stable hazard just gets multiplier 1.0:

```text
growth_rate = (area_now − area_at_window_start) / area_at_window_start / elapsed_seconds
growth_multiplier = 1 + clamp(growth_rate × growth_rate_scale, 0, growth_max_boost)
```

Both factors read from `configs/thresholds.json` (`priority_normalization.hazard_risk`)
and are implemented in `intelligence/priority/engine.py`
(`_zone_risk_multiplier` / `_growth_multiplier`) — see that module's
docstring for the same formulas alongside the code.

### 12.2 Alert latching

`priority`/`band` are always the honest, unlatched instantaneous value —
never held artificially high. A separate `IncidentState.alert_active` flag
(computed in `backend/pipeline.py` via
`NotificationEngine.is_alert_latched()`) stays `True` for
`notification_persistence_seconds` after a real notification fires, so the
dashboard doesn't flicker an alert banner off the instant one noisy frame
dips below threshold. It never re-fires a duplicate notification — that's
still governed entirely by `notification_cooldown_seconds`, unchanged.

---

# 13. Phase 11 — Incident State

Create a single structured state consumed by the dashboard (and by the
notification engine in Phase 12).

Conceptually:

```json
{
  "timestamp": "...",
  "priority": 82,
  "affected_zones": [],
  "people": [],
  "hazards": [],
  "exits": [],
  "congestion": {},
  "contributors": [],
  "confidence": 0.87,
  "uncertainty": false,
  "notification": {
    "status": "not_sent",
    "reason": null
  },
  "timeline": []
}
```

This becomes the bridge between intelligence and UI — and the single object
the notification engine reads to decide whether to alert anyone.

---

# 14. Phase 12 — Notification Engine (new)

## Goal

When an incident crosses a persistent critical condition, automatically
notify the **nearest configured government/emergency service** for that
building — in addition to showing it on the dashboard. This is alerting,
not autonomous dispatch: RESQ tells a real human at a real service that
attention may be needed; it does not command a response.

Pipeline:

```text
Incident State
      ↓
Threshold + persistence check
      ↓
Cooldown check
      ↓
Build explainable payload
      ↓
NotificationProvider.send()
      ↓
Log attempt (sent / failed / suppressed) → Supabase `notifications`
      ↓
Incident State.notification updated → Dashboard
```

## Trigger condition (configs/thresholds.json)

```json
{
  "critical_priority_threshold": 80,
  "notification_persistence_seconds": 10,
  "notification_cooldown_seconds": 120
}
```

- Fire only when `priority >= critical_priority_threshold` **and** that
  condition has held for `notification_persistence_seconds` — never on a
  single noisy frame.
- One notification per escalation: suppress re-firing within
  `notification_cooldown_seconds` unless priority first drops back below
  threshold and rises again, or a materially new contributor appears.

## Payload contract

The notification must carry the same explainability as the dashboard —
never assert more certainty than the detections support:

```json
{
  "building": "…",
  "camera_id": "CAM-01",
  "priority": 82,
  "top_contributors": ["hazard_exposure", "people_in_danger_zone", "exit_obstruction"],
  "affected_zones": ["DANGER-A"],
  "exit_states": {"EXIT-A": "CLEAR", "EXIT-B": "OBSTRUCTED"},
  "confidence": 0.87,
  "uncertainty": false,
  "recipient": {"service": "fire", "name": "…", "channel": "…"},
  "timestamp": "…"
}
```

## Implementation notes

- `intelligence/notification/notifier.py` defines a small
  `NotificationProvider` interface (`send(payload) -> NotificationResult`).
- Ship a `MockProvider` by default — logs to stdout and writes a row to the
  Supabase `notifications` table. The demo must work fully on the mock
  provider alone.
- Real adapters (Twilio SMS, SMTP email, generic webhook) implement the
  same interface — wire one in only if time permits.
- Sending must be **fire-and-forget** (async/background task) — a slow or
  failing notifier must never block detection, tracking, zone, temporal,
  priority, or dashboard updates.
- Recipient lookup comes only from `building/emergency_contacts.json` —
  RESQ does not infer or guess which agency is "nearest"; that mapping is
  configured ahead of time per building.
- Never claim the service has "dispatched" someone or guarantee delivery —
  surface the provider's actual delivery status.

## Definition of Done

- A sustained critical condition (held past
  `notification_persistence_seconds`) produces exactly one notification
  attempt, logged to `notifications`, without blocking the pipeline.
- A brief, non-persistent spike does **not** notify.
- A second sustained critical condition within the cooldown window does
  **not** re-notify unless priority first dropped below threshold.
- The dashboard shows accurate notification status (sent / pending /
  suppressed / failed) sourced from the Incident State, not fabricated.

---

# 15. Phase 13 — Dashboard

The dashboard should be built around the Incident State.

Recommended layout:

```text
┌────────────────────────────────────────────────────┐
│ RESQ                         PRIORITY: 82 / 100    │
├───────────────────────────┬────────────────────────┤
│                           │                        │
│     ANNOTATED VIDEO       │     FLOOR PLAN         │
│                           │                        │
│   Person #17              │    [Danger Zone]       │
│   Person #18              │          ●             │
│   Fire 0.91               │       Exit B           │
│                           │                        │
├───────────────────────────┴────────────────────────┤
│ TOP CONTRIBUTORS                                    │
│ • People in danger zone                             │
│ • Exit B obstruction                                │
│ • Increasing occupancy                              │
├────────────────────────────────────────────────────┤
│ EXIT A: CLEAR   EXIT B: OBSTRUCTED   EXIT C: ?     │
├────────────────────────────────────────────────────┤
│ 🚨 Fire Dept (Zone 3) notified at 14:32:07          │
├────────────────────────────────────────────────────┤
│ TIMELINE                                            │
│ 10:05 Normal → 10:18 Danger → 10:31 Obstruction    │
└────────────────────────────────────────────────────┘
```

---

# 16. Phase 14 — Integration

Connect everything:

```text
Video
 ↓
Detection
 ↓
Tracking
 ↓
Zone
 ↓
Temporal
 ↓
Baseline
 ↓
Priority
 ↓
Incident State
 ↓
Notification
 ↓
Dashboard
```

At this point, the system should operate from one command/process flow.

---

# 17. Phase 15 — Demo Hardening

Do not add new features here.

Test:

### Detection

- People are detected.
- Confidence is reasonable.
- Validated hazard class works.

### Tracking

- IDs persist.
- IDs do not reset unnecessarily.

### Zones

- Entry works.
- Exit works.
- Danger-zone count updates.

### Exits

- Only configured exits are evaluated.
- Obstruction requires persistence.

### Priority

- Score changes when scene conditions change.
- Contributors explain the score.

### Notification

- Notification fires once, after the persistence window, on a sustained
  critical condition.
- Notification does not fire on a brief spike.
- Cooldown prevents duplicate notifications.
- A forced provider failure is logged as "failed", not silently dropped or
  presented as "sent".

### Dashboard

- Video and floor plan remain synchronized.
- Timeline updates.
- Unknown/uncertain state is visible.
- Notification status line reflects the actual notification log.

---

# 18. Final 60-Second Demo Workflow

## 0–10 seconds

```text
Show floor plan
+
Show camera
```

Explain:

> RESQ already knows the configured building zones, exits, camera coverage,
> and the nearest emergency contacts for this building.

## 10–20 seconds

People appear.

Show:

```text
Person #17
Person #18
Person #19
```

and zone occupancy.

## 20–30 seconds

People enter danger zone.

Show:

```text
People in danger zone: 0 → 3
Priority: 34 → 61
```

## 30–40 seconds

Exit B becomes persistently obstructed.

Show:

```text
EXIT B
OCCUPIED
      ↓
OBSTRUCTED
```

## 40–50 seconds

Temporal engine detects deterioration; priority crosses the critical
threshold and holds.

Show:

```text
Scene trend:
STABLE → DETERIORATING

Priority:
61 → 82

🚨 Notifying nearest Fire Dept (Zone 3)…
```

## 50–60 seconds

Show:

```text
HIGH-PRIORITY ZONE

Top contributors:
1. Hazard exposure
2. People in danger zone
3. Exit B obstruction

Exit B: observed obstruction
Exit A: less obstructed in monitored view

🚨 Fire Dept notified at 14:32:07 — confirmation pending

Confidence: X
Human responder decision required.
```

---

# 19. Testing Workflow

## Unit Tests

Test independently:

```text
polygon membership
track state
dwell calculation
occupancy
persistence
priority calculation
uncertainty handling
notification trigger (threshold + persistence)
notification cooldown
notification payload construction
```

## Integration Test

Run:

```text
Video
 ↓
Detection
 ↓
Tracking
 ↓
Zone
 ↓
Temporal
 ↓
Priority
 ↓
Notification
```

and verify the final Incident State, including notification status.

## Demo Test

Run the complete prerecorded scenario from start to finish.

Expected result:

```text
NO MANUAL INTERVENTION
```

---

# 20. Git Workflow

Use small, focused commits.

Recommended branches:

```text
main
  │
  ├── feature/video-ingestion
  ├── feature/detection
  ├── feature/tracking
  ├── feature/zones
  ├── feature/building-model
  ├── feature/temporal-engine
  ├── feature/priority-engine
  ├── feature/notification-engine
  └── feature/dashboard
```

Example commits:

```text
feat: add video ingestion
feat: integrate YOLO detection
feat: add persistent tracking
feat: add polygon zone engine
feat: add building configuration
feat: add temporal scene state
feat: add priority engine
feat: add incident state
feat: add nearest-service notification engine
feat: add responder dashboard
test: add end-to-end demo validation
```

---

# 21. Definition of "DONE"

RESQ MVP is done when one prerecorded emergency video can run through:

```text
VIDEO
 ↓
DETECTION
 ↓
TRACKING
 ↓
ZONE MEMBERSHIP
 ↓
TEMPORAL EVENTS
 ↓
EXIT STATE
 ↓
PRIORITY
 ↓
INCIDENT STATE
 ↓
NOTIFICATION
 ↓
DASHBOARD
```

without manual intervention.

The dashboard must explain:

```text
WHO?
WHAT?
WHERE?
WHAT CHANGED?
IS IT GETTING WORSE?
WHY DOES IT MATTER?
HOW CERTAIN ARE WE?
WAS ANYONE NOTIFIED?
```

---

# 22. Things We Do Not Do During the Hackathon

If a feature does not improve the core vertical slice, defer it.

Do not expand into:

- City-wide command centers
- Autonomous dispatch
- Medical triage
- Automatic blueprint generation
- Universal CCTV support
- Guaranteed evacuation routes
- Universal disaster detection
- Uncontrolled online training
- Notification content that overstates certainty, or claims a service has
  "dispatched" a response

The strongest RESQ demo is a **small, deterministic, explainable system that actually works** — including when it decides to notify someone.
