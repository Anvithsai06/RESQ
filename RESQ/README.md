# RESQ — Real-Time Emergency Scene Intelligence

**SEE THE SCENE. UNDERSTAND THE CHANGE. PRIORITIZE THE RESPONSE.**

RESQ converts emergency video into structured, explainable scene
intelligence for a human responder. It is decision support, not an
autonomous emergency-response system — a human always makes the final call.

```
Emergency Video → Detection → Tracking → Zone Understanding →
Building Context → Temporal Scene State → Priority →
Nearest-Service Notification → Responder Dashboard
```

## What it does

- Detects people and validated hazard classes (YOLO)
- Gives people persistent identities across frames (ByteTrack)
- Maps detections onto predefined building zones, exits, and danger areas
  (OpenCV polygon engine)
- Tracks how the scene changes over time — occupancy, dwell time,
  congestion, exit obstruction (temporal scene-state engine)
- Produces a transparent, decomposable 0–100 priority score with named
  contributors and an explicit uncertainty flag (priority engine)
- **Automatically notifies the nearest configured government/emergency
  service** (police, fire, EMS) when a condition crosses a persistent
  critical threshold — with the same explainability and uncertainty
  disclosure shown on the dashboard, never overstating certainty
- Shows all of the above, live, on a responder dashboard (annotated video +
  floor plan + timeline)

## What it deliberately does not do

- No autonomous evacuation commands or guaranteed-safe routes
- No claim of exact real-world distance from monocular video
- No medical diagnosis or injury detection
- No autonomous drone/robot dispatch
- No claim that the priority score is a clinically or operationally
  validated safety standard
- No notification that asserts more certainty than the underlying
  detections support

See `docs/RESQ_Hackathon_Strategy_PRD.md` §3 and §7 for the full list of
claims RESQ intentionally avoids, and why.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | TypeScript + React + Tailwind CSS |
| Backend API | Python + FastAPI |
| Video / CV | Python + OpenCV |
| Detection | YOLO |
| Tracking | ByteTrack |
| Database | Supabase (PostgreSQL) |
| Realtime updates | Supabase Realtime |
| Storage | Supabase Storage |
| Notifications | Provider-agnostic (mock provider for demo; Twilio/SMTP/webhook adapters) |
| Coding agent | Claude Code — see `CLAUDE.md` |

## Getting started

```bash
# 1. Clone and enter the repo
git clone <your-fork-url> resq && cd resq

# 2. Copy env template and fill in real values
cp .env.example .env

# 3. Backend + vision (Python)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Frontend
cd frontend && npm install && cd ..

# 5. Run the backend API
uvicorn backend.main:app --reload

# 6. Run the frontend dashboard
cd frontend && npm run dev
```

Full phase-by-phase build plan: see [`WORKFLOW.md`](./WORKFLOW.md).
Agent instructions for Claude Code: see [`CLAUDE.md`](./CLAUDE.md).

## Project structure

```
resq/
├── frontend/        TypeScript + React dashboard
├── backend/         FastAPI app (routes, services, schemas, config)
├── vision/          detection/ tracking/ zones/ video/
├── intelligence/    temporal/ baseline/ priority/ incident/ notification/
├── building/        building.json cameras.json zones.json exits.json emergency_contacts.json
├── configs/         thresholds.json model_versions.json
├── models/          YOLO weights (gitignored)
├── data/            demo videos / frames (gitignored except fixtures)
├── supabase/migrations/
├── tests/           unit/ integration/
├── docs/            original PRDs and strategy docs (reference only)
├── CLAUDE.md        instructions Claude Code reads automatically
├── WORKFLOW.md       the build plan
└── .env.example
```

## Configuration

RESQ is calibrated to one known building/camera setup for the demo — it
does not claim universal CCTV support. All scene-specific configuration
lives in `building/`:

- `building.json` — floors, zone graph, connectivity
- `cameras.json` — camera position, orientation, covered zones
- `zones.json` — image-space polygons mapped to building zones
- `exits.json` — which doors are configured/trusted as emergency exits
- `emergency_contacts.json` — nearest police/fire/EMS contact per building,
  used by the notification engine (see `CLAUDE.md` → "notify the nearest
  government service")

Thresholds (priority weights, persistence windows, notification cooldown)
live in `configs/thresholds.json`.

## Status

Hackathon MVP — one prerecorded emergency video running the full pipeline
end-to-end without manual intervention. See `WORKFLOW.md` §16 for the demo
hardening checklist and §17 for the 60-second demo script.
