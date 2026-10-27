**RESQ**

**Building-Aware Emergency Scene Intelligence**

*Product Requirements Document • Hackathon MVP + Deployment
Architecture*

One-line thesis: RESQ is a building-specific, explainable emergency
intelligence layer that combines computer vision, persistent tracking, a
digital building map, configured camera zones, temporal scene analysis,
and historical baselines to help human responders understand what is
changing, where attention is needed, and which predefined exits/zones
appear usable from the cameras.

# 1. Product Decision: What Are We Building?

RESQ should NOT start as a city-wide disaster-management platform. The
strongest version is a building-specific emergency intelligence system.
A building is onboarded once with its floor plans, camera
locations/views, exits, stairways, corridors, restricted areas, safe
zones, and other relevant landmarks. RESQ then interprets camera footage
against that known environment.

This solves several weaknesses of the generic-CCTV concept: the system
no longer has to infer the building layout from pixels, guess which
doors are exits, or invent routes. The building configuration provides
the spatial context; computer vision provides the changing scene state.

Important technical distinction: the blueprint is not \'training data\'
for YOLO. It is a building configuration / spatial model. The ML models
detect visual entities; the building model tells RESQ what those
entities mean in the configured environment.

# 2. Target Deployment

-   Primary target: one campus/college building, office building,
    hospital block, mall, warehouse, or similar controlled facility.

-   Hackathon target: one representative building with one or a small
    number of fixed camera views and one prerecorded emergency scenario.

-   Future target: multi-building campuses where each building has its
    own calibrated map and camera registry, with a central responder
    console.

-   Not an MVP target: city-wide autonomous emergency coordination. That
    requires integrations, GIS, communications infrastructure,
    validation, and operational governance far beyond the hackathon.

# 3. Core Product Concept --- Building Digital Twin + Live Scene State

RESQ has two complementary layers:

-   Static layer --- Building Digital Twin: floor plans, rooms,
    corridors, exits, stairs, restricted areas, safe zones, camera
    locations, camera polygons, and known connectivity between zones.

-   Dynamic layer --- Emergency Scene State: people, hazards, obstacles,
    tracking IDs, zone occupancy, congestion, obstruction persistence,
    hazard persistence, temporal changes, confidence, and priority.

The product therefore answers a stronger question than \'What objects
are in this frame?\': \'Given what we know about this building, what has
changed in the emergency scene, where is the situation deteriorating,
and what information should a human responder inspect first?\'

# 4. Problem Statement

During an emergency, fixed cameras generate large amounts of visual
information but do not automatically convert it into a structured,
time-aware operating picture. Responders may need to manually inspect
multiple feeds, count people, notice congestion, identify changing
hazards, and determine which known areas are becoming obstructed.

RESQ converts those feeds into a continuously updated, explainable
building scene state while keeping the human responder as the final
decision-maker.

# 5. The Killer Feature

Building-Aware Temporal Emergency State Engine. The differentiator is
not YOLO, tracking, or a dashboard individually. It is the combination
of perception + persistent identity + building zones + temporal change +
historical baseline + explainable prioritization.

-   Perception: detect selected classes such as people and validated
    hazards.

-   Tracking: maintain persistent person IDs and trajectories across
    frames.

-   Building reasoning: associate camera observations with predefined
    floor-plan zones.

-   Temporal reasoning: detect entry, exit, dwell time, increasing
    occupancy, worsening congestion, persistent hazard evidence, and
    changing obstruction states.

-   Baseline reasoning: compare current conditions against
    normal/learned scene baselines for that camera/zone.

-   Decision support: produce a bounded priority index with explicit
    contributors and reason codes.

-   Responder view: show what changed, where it changed, how many
    entities are involved, confidence/uncertainty, and relevant building
    context.

# 6. Building Onboarding / Blueprint Pipeline

A building is onboarded before operational use. RESQ does not attempt to
discover the entire floor plan from a generic CCTV feed.

1\. Upload floor plan / blueprint or structured building map.

2\. Define floors, rooms, corridors, stairs, elevators, exits,
assembly/safe areas, restricted areas, and important landmarks.

3\. Register each camera with its floor, physical/approximate location,
viewing direction, and covered zones.

4\. For each camera, draw image-space polygons corresponding to
important building zones visible in that camera.

5\. Associate camera zones with building-map zones where the
relationship is known.

6\. Mark emergency exits explicitly; a door is never treated as an exit
merely because it looks like a door.

7\. Define valid zone transitions/connectivity from the building plan.

8\. Set scene-specific thresholds and operating assumptions.

9\. Run a calibration/validation procedure using normal footage before
emergency use.

This architecture directly addresses the \'generic camera cannot infer a
floor plan\' criticism: the floor plan is supplied as trusted
configuration, while video is used to observe dynamic conditions.

# 7. How Daily Raw Data Should Be Used

Do NOT continuously retrain the core detector on every day\'s raw CCTV
footage. That creates drift, label-quality problems, privacy concerns,
and unpredictable model behavior.

-   Daily raw footage → scene statistics: occupancy patterns, normal
    crowd density, typical movement, typical zone usage, and camera
    health.

-   Daily observations → baseline updates: learn what \'normal\' looks
    like for each camera/zone/time window.

-   New labeled emergency footage → controlled model
    evaluation/retraining dataset, reviewed before deployment.

-   Confirmed false positives/false negatives → candidate hard examples
    for a versioned training set.

-   Model updates → offline validation → shadow testing → approved
    deployment, not uncontrolled live retraining.

This creates a safer learning loop: RESQ becomes increasingly
building-aware through historical scene baselines without pretending
that unsupervised daily CCTV automatically makes the vision model
smarter.

# 8. Supported Emergency Intelligence

  ---------------------------------------------------------------------------------------------
  Signal            Measured From           Output                            Boundary
  ----------------- ----------------------- --------------------------------- -----------------
  People            YOLO detections +       Current/unique tracked people     Detection
                    tracking                                                  performance is
                                                                              scene-dependent

  Hazard            Validated detector +    Hazard                            Smoke/fire
                    persistence             presence/confidence/persistence   classes only if
                                                                              validated

  Danger-zone       Tracked IDs +           People inside configured danger   Image-space zone
  occupancy         configured polygons     zones                             membership

  Crowding          Zone occupancy +        Density/occupancy state           Not a clinical
                    temporal baseline                                         crowd-safety
                                                                              standard

  Exit state        Configured exit         CLEAR / OCCUPIED / OBSTRUCTED /   Only for
                    polygon + persistent    UNCERTAIN                         explicitly
                    occupancy/obstruction                                     configured exits
                    evidence                                                  

  Scene             Time-series metrics     Increasing/decreasing/stable      Depends on
  deterioration                             state                             observation
                                                                              window

  Priority          Deterministic weighted  0--100 prototype priority index   Not a validated
                    signals                                                   emergency
                                                                              standard
  ---------------------------------------------------------------------------------------------

# 9. Risk / Priority Index

RESQ should call this a \'Priority Index\' rather than implying a
medically or operationally validated risk score. It is deterministic,
bounded, transparent, and tuned for the selected building scenario.

Example: Priority = 0.40 × Hazard Exposure + 0.25 ×
People-in-Danger-Zones + 0.20 × Congestion + 0.15 × Exit Obstruction.

-   Each component is normalized to 0--100 using documented scene
    thresholds.

-   Every score displays its top contributors.

-   The dashboard shows score history, not just a single number.

-   An uncertainty penalty/state can prevent weak evidence from
    appearing as high-confidence truth.

-   Thresholds are configuration, not universal safety constants.

# 10. Route Intelligence --- Solve the Route Problem Properly

The building blueprint enables a future route-planning layer, but the
MVP should not claim autonomous evacuation. Instead, RESQ can maintain a
graph of known zones and exits and calculate an \'observed
availability\' signal for predefined exits.

-   Floor-plan graph: nodes = configured rooms/zones; edges = known
    corridors/stairs/connections.

-   Camera observations update obstruction/occupancy state on graph
    nodes or edges where camera coverage exists.

-   The system can rank predefined exits by observed obstruction state
    and known connectivity.

-   If a path contains an unobserved segment, it is explicitly marked
    \'UNKNOWN\', not assumed clear.

-   Responder output: \'Exit B has persistent observed obstruction; Exit
    A appears less obstructed in monitored areas.\'

-   No output should state that a route is guaranteed safe.

# 11. Architecture

-   Video ingestion → frame sampling

-   YOLO / selected CV models → detections + confidence

-   ByteTrack / compatible tracker → persistent IDs + trajectories

-   OpenCV zone engine → polygon occupancy, overlap, image-space
    relationships

-   Building Model → floor-plan zones, exits, connectivity, camera
    registry

-   Temporal Scene-State Engine → rolling counts, dwell time, crowding,
    hazard persistence, obstruction persistence, deterioration

-   Historical Baseline Engine → normal occupancy/movement patterns by
    zone/time

-   Explainable Priority Engine → deterministic index + reason codes +
    uncertainty

-   Responder Dashboard → annotated video + floor-plan context +
    metrics + alerts + timeline

# 12. Data Model

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

# 13. Dashboard Requirements

-   Annotated live/prerecorded emergency video with bounding boxes,
    track IDs, trajectories, and configured zones.

-   Building/floor-plan panel showing camera coverage and affected
    zones.

-   CRITICAL / HIGH / MODERATE / LOW priority state plus 0--100
    prototype index.

-   People detected and unique tracked people.

-   People currently in danger zones.

-   Crowd density/occupancy by zone.

-   Hazard detections with confidence and persistence.

-   Exit A/B/etc. status: CLEAR / OCCUPIED / OBSTRUCTED / UNCERTAIN.

-   Top 3 reasons for current priority.

-   Scene timeline: improving / deteriorating / stable.

-   AI confidence and uncertainty indicator.

-   Camera health / stale-feed indicator.

# 14. Responsible AI / Safety Boundaries

-   No exact physical distance claims from monocular video unless an
    independently validated calibration model is available.

-   No injury or medical-condition detection.

-   No inferred floor plan from arbitrary CCTV.

-   No autonomous evacuation command.

-   No assumption that a detected door is an emergency exit.

-   No conversion of pixel distance into real-world danger without
    calibration.

-   No claim that the priority index is clinically, legally, or
    operationally validated.

-   No universal performance claim across all disaster environments.

-   Unknown is a valid system output.

-   Human responder remains responsible for final emergency decisions.

# 15. How the Major Negative Arguments Are Solved

  -----------------------------------------------------------------------
  Criticism                           RESQ Design Response
  ----------------------------------- -----------------------------------
  Too many CV tasks                   Building-specific scope + validated
                                      class activation + optional hazard
                                      modules + one controlled scene.

  Smoke/fire ambiguity                Confidence thresholds, temporal
                                      persistence, uncertainty state, and
                                      explicit validation before enabling
                                      a class.

  Arbitrary score                     Transparent prototype Priority
                                      Index with named normalized
                                      contributors and history.

  Pixel proximity                     Use only configured image-space
                                      zones in MVP; physical
                                      interpretation requires
                                      calibration.

  Blocked exit                        Exit is defined by the building
                                      configuration; obstruction is
                                      persistent monitored
                                      overlap/occupancy.

  Route recommendation                Use the known building graph only
                                      for observed availability/ranking;
                                      unknown segments stay unknown.

  Dashboard glued to YOLO             Temporal scene-state + building
                                      model + historical baseline +
                                      explainable events are the product
                                      layer.

  Tracking lacks value                Tracking powers dwell time, zone
                                      entry, congestion trends, movement
                                      direction and temporal events.

  Dataset mismatch                    One controlled building domain for
                                      MVP; separate validated vs
                                      experimental detectors.

  False positives                     Persistence + confidence +
                                      uncertainty + human review rather
                                      than single-frame alerts.

  Real-time performance               Frame sampling, lightweight models,
                                      bounded dashboard refresh and
                                      prerecorded fallback.

  Huge scope                          One building, one floor or camera
                                      cluster, one incident scenario, one
                                      end-to-end vertical slice.
  -----------------------------------------------------------------------

# 16. MVP Scope for the Hackathon

-   One building.

-   One floor if time is tight; multiple floors only if the core
    pipeline is already stable.

-   One or two fixed camera views.

-   One emergency video scenario.

-   People detection + stable tracking as mandatory.

-   At least one validated hazard class; fire/smoke are optional until
    validated on the selected footage.

-   Configured danger zone(s).

-   Configured exits.

-   Temporal congestion and obstruction state.

-   Building floor-plan visualization.

-   Explainable Priority Index.

-   Complete prerecorded demo with no manual intervention.

-   Optional: historical baseline from normal footage.

# 17. What We Do NOT Build in the Hackathon

-   City-wide command center.

-   Autonomous drone/robot dispatch.

-   Automatic emergency-service communication.

-   Universal CCTV compatibility claims.

-   Medical triage.

-   Automatic blueprint generation from video.

-   Uncontrolled online model retraining.

-   Guaranteed evacuation routing.

-   Multi-disaster universal model unless the selected data genuinely
    supports it.

# 18. 60-Second Judge Demo

  -----------------------------------------------------------------------
  Time                                Demo
  ----------------------------------- -----------------------------------
  0--10s                              Show the building floor plan and
                                      camera view. RESQ already knows the
                                      configured exits, danger zones and
                                      camera coverage.

  10--20s                             People are detected and tracked
                                      with persistent IDs. The dashboard
                                      shows unique people and zone
                                      occupancy.

  20--30s                             People enter a configured danger
                                      zone. The affected-zone count and
                                      priority contributors change.

  30--40s                             A configured exit becomes
                                      persistently occupied/obstructed in
                                      the monitored camera view. Exit
                                      state changes.

  40--50s                             Temporal engine detects
                                      deterioration compared with the
                                      recent scene/baseline and updates
                                      the Priority Index.

  50--60s                             RESQ highlights the
                                      highest-priority zone and shows:
                                      \'Exit B: observed obstruction.
                                      Exit A: less obstructed in
                                      monitored view. Confidence: X.
                                      Human responder decision
                                      required.\'
  -----------------------------------------------------------------------

# 19. Technical Novelty Claim

The novelty claim should be precise: RESQ is a building-aware temporal
scene-state engine for emergency video. YOLO and tracking are perception
primitives. The innovation is the structured fusion of those
observations with a known building model, configured camera zones,
temporal events, historical baselines, uncertainty, and explainable
prioritization.

The strongest answer to \'Why not just YOLO + ByteTrack + OpenCV?\' is:
because those tools produce observations; RESQ maintains a
building-specific state of the incident and explains how that state is
changing over time.

# 20. Acceptance Criteria

-   Stable tracking IDs across consecutive frames in the demo.

-   Building zones are loaded from configuration and mapped to camera
    polygons.

-   Danger-zone entry/exit is detected from polygon membership.

-   People-at-risk changes when tracked people enter/leave configured
    danger zones.

-   Crowd state changes as zone occupancy changes.

-   Exit state changes only for configured exits and only after
    persistent evidence.

-   Hazard state includes confidence and persistence.

-   Priority Index changes when measurable scene conditions change.

-   Every priority state has named contributors/reasons.

-   Floor-plan context and camera evidence are visible together.

-   Unknown/uncertain conditions are surfaced explicitly.

-   Historical baseline can be displayed where available.

-   The full prerecorded demo runs end-to-end without manual
    intervention.

# 21. Post-Hackathon Roadmap

-   Phase 1 --- Hackathon: one building, one incident, deterministic
    scene intelligence.

-   Phase 2 --- Building deployment: multiple cameras/floors, stronger
    calibration, camera-health monitoring, access control and privacy
    controls.

-   Phase 3 --- Learning layer: validated hard-example collection,
    offline model improvement, building-specific baselines, shadow
    deployments.

-   Phase 4 --- Campus: multiple buildings with a central responder
    console.

-   Phase 5 --- Multi-site: reusable building onboarding, GIS/BIM
    integrations, standardized incident APIs, rigorous validation.

-   Only after substantial validation should broader operational claims
    be considered.

# 22. Final Product Positioning

**RESQ is not an AI firefighter.** It is the intelligence layer between
building cameras and human responders. The building blueprint provides
trusted spatial context. Computer vision observes the live scene.
Tracking provides identity over time. Temporal reasoning detects
deterioration. Historical data defines normal patterns. The explainable
priority engine tells responders what changed and why it matters.

**SEE THE SCENE. UNDERSTAND THE CHANGE. PRIORITIZE THE RESPONSE.**

# 23. Hackathon Execution Rule

Do not divide the team into isolated feature islands. Build along the
dependency chain: building configuration → perception → tracking → zone
engine → temporal scene state → priority engine → dashboard →
deterministic demo. The first milestone is a working annotated video
with stable detections; the final milestone is the building-aware
scene-state demonstration.
