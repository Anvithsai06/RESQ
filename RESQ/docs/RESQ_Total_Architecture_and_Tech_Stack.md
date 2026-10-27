**RESQ**

**Building-Aware Emergency Scene Intelligence**

*Total Architecture, Technology Stack & Implementation Blueprint\
Hackathon MVP*

# 1. Architecture Decision

RESQ is a building-specific, explainable emergency intelligence layer.
It combines computer vision, persistent tracking, a configured building
model, camera zones, temporal scene analysis, historical baselines and
explainable prioritization so a human responder can understand what is
changing, where attention is needed, and which monitored exits/zones
appear relevant.

The architecture is intentionally one controlled vertical slice: one
building, one floor if necessary, one or two fixed camera views, one
prerecorded emergency scenario, mandatory people detection/tracking, at
least one validated hazard class, configured danger zones/exits,
temporal congestion/obstruction, floor-plan visualization and an
explainable Priority Index.

# 2. End-to-End Architecture

VIDEO SOURCE\
CCTV / Prerecorded Video\
\|\
v\
VIDEO INGESTION\
Decode -\> Frame Sampling -\> Resize -\> Timestamp\
\|\
v\
COMPUTER VISION\
YOLO / Validated CV Models\
\|\
v\
TRACKING\
ByteTrack / Compatible Tracker\
Persistent IDs + Trajectories\
\|\
v\
ZONE ENGINE\
OpenCV Polygons\
Zone Membership + Occupancy + Image-Space Relations\
\|\
+\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\--+\
\| \|\
v v\
BUILDING MODEL TEMPORAL SCENE ENGINE\
Floors / Zones Entry / Exit / Dwell\
Exits / Cameras Occupancy / Congestion\
Connectivity Hazard / Obstruction Persistence\
\| Deterioration\
+\-\-\-\-\-\-\-\-\--+\-\-\-\-\-\-\-\-\-\--+\
\|\
v\
HISTORICAL BASELINE ENGINE\
Normal occupancy / movement / zone usage / time windows\
\|\
v\
EXPLAINABLE PRIORITY ENGINE\
0-100 Priority + Contributors + Reason Codes + Uncertainty\
\|\
v\
INCIDENT STATE\
Priority / Affected Zones / People / Hazards / Exits / Timeline\
\|\
v\
RESQ RESPONDER DASHBOARD\
Annotated Video + Floor Plan + Metrics + Alerts + Timeline\
\|\
v\
HUMAN RESPONDER\
Final decision remains human-controlled.

# 3. Technology Stack --- What Is Actually Supported by the Source

  -----------------------------------------------------------------------
  Layer                   Technology / Approach   Status
  ----------------------- ----------------------- -----------------------
  Computer Vision         YOLO / selected         Explicitly specified
                          validated CV models     

  Object Tracking         ByteTrack / compatible  Explicitly specified
                          tracker                 

  Image / Zone Processing OpenCV; image-space     Explicitly specified
                          polygons                

  Video Input             CCTV / prerecorded      Explicitly specified
                          video                   

  Building Model          Structured building     Explicitly specified
                          configuration / digital 
                          twin                    

  Temporal Intelligence   Custom Temporal         Architecture
                          Scene-State Engine      requirement

  Historical Behavior     Custom Historical       Architecture
                          Baseline Engine         requirement

  Prioritization          Deterministic           Architecture
                          Explainable Priority    requirement
                          Engine                  

  Incident State          Structured current      Data-model requirement
                          incident state          

  Dashboard               Responder dashboard     Product requirement
                          with video + floor      
                          plan + metrics          

  Route Intelligence      Configured zone graph + MVP-bounded requirement
                          observed availability   
  -----------------------------------------------------------------------

# 4. Technology Decisions NOT Specified in the Source

Do not present the following as already-decided technologies. The source
documents define the architecture and CV stack, but do not commit to a
frontend framework, backend framework, database, cache, WebSocket/REST
choice, cloud provider, containerization, object storage, message queue,
monitoring stack, CI/CD system, floor-plan rendering library, or
charting library.

-   Frontend framework

-   Backend language/framework

-   Database

-   Cache

-   REST vs WebSocket

-   Authentication/authorization implementation

-   ORM

-   Video streaming protocol

-   Containerization

-   Cloud/GPU provider

-   Object/file storage

-   Message queue

-   Monitoring/logging

-   CI/CD

-   Floor-plan rendering library

-   Dashboard charting library

# 5. Core Modules

**Video Ingestion:** Decode source video, sample frames, handle
resolution/timestamps, and expose camera/feed health.

**Perception Engine:** Run YOLO/validated detectors and produce class,
confidence and bounding-box observations.

**Tracking Engine:** Run ByteTrack/compatible tracking to maintain
persistent IDs and trajectories.

**Zone Engine:** Apply configured image-space polygons to determine zone
membership, occupancy and configured exit/danger-zone relationships.

**Building Digital Twin:** Store trusted floors, rooms, corridors,
stairs, exits, safe/restricted areas, camera registry and zone
connectivity.

**Temporal Scene-State Engine:** Convert observations into
entry/exit/dwell, occupancy, congestion, hazard persistence, obstruction
persistence and deterioration states.

**Historical Baseline Engine:** Represent normal occupancy, movement,
zone usage and time-window behavior. Daily raw footage should update
scene statistics, not uncontrolled detector retraining.

**Explainable Priority Engine:** Compute a bounded deterministic
Priority Index and expose named contributors, reason codes and
uncertainty.

**Incident State:** Maintain the current structured state: priority,
contributors, uncertainty, affected zones and timeline.

**Responder Dashboard:** Show annotated video, building/floor context,
priority, people, hazards, crowding, exits, reasons, timeline,
confidence and camera health.

# 6. Data Model

-   Building: building_id, name, floors, versioned blueprint.

-   Zone: zone_id, floor, type, polygon/map geometry, connected zones,
    priority metadata.

-   Exit: exit_id, floor, map location, camera-visible zones, configured
    status rules.

-   Camera: camera_id, building_id, floor, position, orientation,
    stream/source, calibration metadata.

-   Observation: timestamp, camera_id, class, confidence, bounding box,
    track_id.

-   ZoneEvent: entry/exit/dwell/occupancy/obstruction/hazard event with
    timestamp and confidence.

-   Baseline: zone/camera/time-window statistics for normal occupancy
    and movement.

-   IncidentState: current priority, contributors, uncertainty, affected
    zones, timeline.

-   ModelVersion: detector/tracker versions, validation metrics,
    deployment status.

# 7. Building Onboarding Pipeline

1\. Upload floor plan / blueprint or structured building map.

2\. Define floors, rooms, corridors, stairs, elevators, exits,
assembly/safe areas, restricted areas and landmarks.

3\. Register each camera with floor, approximate/physical position,
viewing direction and covered zones.

4\. For each camera, draw image-space polygons for important visible
building zones.

5\. Associate camera zones with building-map zones where the
relationship is known.

6\. Explicitly mark emergency exits; a generic door is never assumed to
be an exit.

7\. Define valid zone transitions/connectivity from the building plan.

8\. Set scene-specific thresholds and operating assumptions.

9\. Run calibration/validation using normal footage before emergency
use.

# 8. CV → Intelligence Data Flow

Frame\
↓\
YOLO detection\
↓\
{class, confidence, bbox, timestamp}\
↓\
ByteTrack\
↓\
{track_id, trajectory}\
↓\
OpenCV polygon membership\
↓\
{zone, danger_zone, exit_zone, occupancy}\
↓\
Temporal state\
↓\
{entry, exit, dwell, congestion, persistence, deterioration}\
↓\
Historical baseline comparison\
↓\
Explainable Priority Engine\
↓\
IncidentState\
↓\
Dashboard

# 9. Priority Index

The documented prototype example is:

**Priority = 0.40 × Hazard Exposure + 0.25 × People-in-Danger-Zones +
0.20 × Congestion + 0.15 × Exit Obstruction**

Each component is normalized to 0--100 using documented scene
thresholds. The dashboard should show score history, top
contributors/reasons and uncertainty. This is a prototype Priority
Index, not a clinically, legally or operationally validated emergency
risk score.

# 10. Exit / Route Intelligence

The MVP does not guarantee evacuation routes. The building graph uses
configured zones as nodes and known corridors/stairs/connections as
edges. Camera observations can update obstruction/occupancy for
monitored segments. A path containing an unobserved segment remains
UNKNOWN. The responder output should therefore describe observed
availability, not guaranteed safety.

# 11. Dashboard Requirements

-   Annotated live/prerecorded emergency video with bounding boxes,
    track IDs, trajectories and configured zones.

-   Building/floor-plan panel showing camera coverage and affected
    zones.

-   CRITICAL / HIGH / MODERATE / LOW state plus 0--100 prototype
    Priority Index.

-   People detected and unique tracked people.

-   People currently in danger zones.

-   Crowd density/occupancy by zone.

-   Hazard detections with confidence and persistence.

-   Exit states: CLEAR / OCCUPIED / OBSTRUCTED / UNCERTAIN.

-   Top 3 reasons for current priority.

-   Scene timeline: improving / deteriorating / stable.

-   AI confidence and uncertainty indicator.

-   Camera health / stale-feed indicator.

# 12. Hackathon Acceptance Criteria

-   Stable tracking IDs across consecutive frames.

-   Building zones load from configuration and map to camera polygons.

-   Danger-zone entry/exit is detected through polygon membership.

-   People-at-risk changes as tracked people enter/leave danger zones.

-   Crowd state changes as zone occupancy changes.

-   Exit state changes only for configured exits and persistent
    evidence.

-   Hazard state includes confidence and persistence.

-   Priority Index changes when measurable scene conditions change.

-   Every priority state has named contributors/reasons.

-   Floor-plan context and camera evidence appear together.

-   Unknown/uncertain conditions are surfaced explicitly.

-   Historical baseline can be displayed when available.

-   Full prerecorded demo runs end-to-end without manual intervention.

# 13. Hackathon Scope --- LOCK THIS

-   1 building

-   1 floor if time is tight

-   1--2 fixed camera views

-   1 prerecorded emergency scenario

-   People detection + stable tracking mandatory

-   At least one validated hazard class

-   Configured danger zones

-   Configured exits

-   Temporal congestion and obstruction state

-   Building floor-plan visualization

-   Explainable Priority Index

-   Complete prerecorded demo without manual intervention

-   Historical baseline optional

# 14. Explicit Non-Goals

-   City-wide command center

-   Autonomous drone/robot dispatch

-   Automatic emergency-service communication

-   Universal CCTV compatibility claims

-   Medical triage

-   Automatic blueprint generation from video

-   Uncontrolled online model retraining

-   Guaranteed evacuation routing

-   Universal multi-disaster model without supporting data

# 15. Responsible AI / Safety Boundaries

-   No exact physical-distance claims from monocular video without
    independently validated calibration.

-   No injury or medical-condition detection.

-   No inferred floor plan from arbitrary CCTV.

-   No autonomous evacuation command.

-   No assumption that a detected door is an emergency exit.

-   No universal performance claim across all disaster environments.

-   Unknown is a valid system output.

-   Human responder remains responsible for final emergency decisions.

# 16. What RESQ\'s Novelty Actually Is

YOLO, tracking and OpenCV are perception primitives. The product novelty
is the structured fusion of detection, persistent tracking, building
configuration, configured camera zones, temporal events, historical
baselines, uncertainty and explainable prioritization into a
building-specific incident state.

**BUILDING + CAMERA CONTEXT + DETECTION + TRACKING + ZONES + TEMPORAL
EVENTS + BASELINE + UNCERTAINTY + EXPLAINABLE PRIORITY → BUILDING-AWARE
INCIDENT STATE**

# 17. Deployment Roadmap

**Phase 1 --- Hackathon:** 1 building, 1 incident, 1--2 cameras,
deterministic scene intelligence.

**Phase 2 --- Building Deployment:** Multiple cameras/floors, stronger
calibration, camera health, privacy controls and access control.

**Phase 3 --- Learning Layer:** Validated hard examples, offline model
improvement, building baselines and shadow deployment.

**Phase 4 --- Campus:** Multiple buildings with a central responder
console.

**Phase 5 --- Multi-Site:** Reusable building onboarding, GIS/BIM
integration, incident APIs and rigorous validation.

# 18. Final Architecture Status

LOCKED FROM SOURCE: the product boundary, CV pipeline, tracking
approach, building model, zone engine, temporal engine, historical
baseline concept, explainable priority concept, data entities, dashboard
requirements, MVP scope and safety boundaries.

NOT LOCKED IN SOURCE: frontend/backend framework, database, API
transport, deployment platform, containerization, storage,
authentication, monitoring, CI/CD and supporting UI libraries. These
must be selected as implementation decisions rather than presented as
facts from the PRD.

# 19. Final Product Positioning

RESQ is not an AI firefighter. It is the intelligence layer between
building cameras and human responders. The building blueprint provides
trusted spatial context; computer vision observes the changing scene;
tracking provides persistent identity; temporal reasoning detects
change; historical data defines normal behavior; and the explainable
Priority Engine tells responders what changed, where it changed, why it
matters, how certain the system is, and what information should be
inspected first.

**SEE THE SCENE. UNDERSTAND THE CHANGE. PRIORITIZE THE RESPONSE.**
