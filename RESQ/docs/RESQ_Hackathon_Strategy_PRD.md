**RESQ**

**Real-Time Emergency Scene Intelligence**

*Hackathon Strategy + Technical PRD*

**One-line thesis:** RESQ does not try to be an autonomous
emergency-response system. It converts emergency video into structured,
explainable scene intelligence that helps a human responder understand
what is happening, where attention is needed, and which predefined safe
zones appear usable.

# 1. The Problem We Are Actually Solving

Emergency footage is information-rich but decision-poor. A responder
watching a camera feed must manually notice people, hazards, congestion,
blocked areas and changes over time. RESQ turns that raw video into a
continuously updated scene state.

-   Input: fixed or recorded emergency video.

-   Output: detected entities, tracked movement, zone occupancy, hazard
    proximity in image space, congestion, obstruction state and an
    explainable priority score.

-   Human remains the decision-maker. RESQ provides intelligence, not
    autonomous evacuation commands.

# 2. The Killer Feature: Dynamic Emergency Scene State

The differentiator is not \'YOLO + dashboard\'. The core feature is a
temporal scene-state engine that combines CV observations across frames
and converts them into explainable changes in emergency priority.

-   Per-frame perception: people, fire/smoke or other selected hazard
    classes, obstacles and predefined scene landmarks.

-   Tracking: persistent person IDs and trajectories.

-   Spatial reasoning: predefined danger, exit and obstruction zones
    mapped onto the camera view.

-   Temporal reasoning: detects worsening crowding, increasing hazard
    presence, repeated occupation of danger zones and exit degradation.

-   Decision layer: converts those measurable signals into a transparent
    priority score with reasons.

-   Responder view: \'what changed, where, how many, and why this area
    is prioritized.\'

**Innovation claim:** RESQ is a video-to-scene-state system, not a
collection of object counters. Its value comes from combining
perception + identity over time + spatial zones + temporal change +
explainable prioritization.

# 3. What We Will NOT Claim

These boundaries make the project stronger, not weaker.

-   No claim of exact physical distance from monocular video.

-   No claim of detecting injuries or medical condition.

-   No claim that a generic camera can infer a true floor plan.

-   No claim of autonomous evacuation decisions.

-   No claim that a detected door is automatically a usable emergency
    exit.

-   No claim that pixel proximity equals real-world proximity.

-   No claim that the risk score is a clinically or operationally
    validated emergency standard.

-   No claim of universal performance across every disaster environment.

**Positioning:** The demo is a decision-support prototype operating
under explicitly defined camera and scene assumptions.

# 4. Scope Control: The Demo Environment

To avoid the dataset and reliability trap, the MVP uses a controlled
emergency scene with a known camera view. Scene-specific zones are
configured once for the demo.

-   Camera: one fixed viewpoint or one prerecorded emergency video.

-   Zones: Danger Zone A/B, Exit A/B, Obstruction Zone(s), Safe
    Observation Area.

-   Known labels: only classes supported by the chosen model/dataset are
    activated.

-   If fire/smoke data is weak, the demo prioritizes the strongest
    validated hazard detector rather than pretending every class is
    equally reliable.

-   Every high-level conclusion is traceable to visible CV evidence.

# 5. Technical Architecture

-   Video Input → frame sampling

-   YOLO detector → object detections + confidence

-   ByteTrack/compatible tracker → persistent IDs + trajectories

-   OpenCV zone engine → region occupancy, overlap and spatial
    relationships

-   Temporal Scene-State Engine → rolling counts, density, hazard growth
    and exit obstruction changes

-   Explainable Risk Engine → weighted priority score + reason codes

-   Streamlit/React dashboard → annotated video + live intelligence
    panel

# 6. The Risk Score Is Explainable

The score is explicitly presented as a prototype prioritization index,
not a universal safety standard. It is deterministic, bounded and
decomposable.

**Example formula:** Risk = 0.40 Hazard Exposure + 0.25 People at Risk +
0.20 Congestion + 0.15 Exit Obstruction. Each component is normalized to
0--100 using scene-defined measurable thresholds.

-   Every score shows its contributors.

-   Example: 87/100 → Hazard Exposure 92, People at Risk 84, Congestion
    78, Exit Obstruction 91.

-   Score changes are shown over time so judges can see that the system
    reacts to scene changes.

-   Thresholds are documented in the demo and can be tuned for the
    controlled scenario.

# 7. How We Defuse the Major Technical Criticisms

  --------------------------------------------------------------------------
  Criticism               Weak Version            RESQ Design Response
  ----------------------- ----------------------- --------------------------
  Too many CV tasks       Detect everything at    Use a controlled scene,
                          once.                   prioritize validated
                                                  classes, and make every
                                                  additional detector
                                                  optional.

  Smoke/fire ambiguity    Treat model output as   Use confidence thresholds,
                          truth.                  temporal persistence,
                                                  visible evidence and
                                                  explicit \'uncertain\'
                                                  states.

  Arbitrary score         Show one unexplained    Use a transparent formula,
                          number.                 normalized components and
                                                  reason codes.

  Pixel distance issue    Claim real-world        Use image-space proximity
                          distance.               only and label it as such.

  Blocked exit issue      Infer an exit           Predefine exit zones;
                          automatically.          obstruction means detected
                                                  occupancy/objects
                                                  overlapping the configured
                                                  zone.

  Unsafe route            Tell people where to    Report relative exit
  recommendation          evacuate.               availability/obstruction
                                                  only; no autonomous route
                                                  command.

  Dashboard glued to YOLO Boxes + counters.       Temporal scene-state
                                                  engine creates changing
                                                  conditions and explainable
                                                  priorities.

  Tracking novelty        IDs for decoration.     Use trajectories to
                                                  measure dwell time, entry
                                                  into danger zones and
                                                  crowd movement.

  Dataset mismatch        Train on unrelated      Use a controlled demo
                          scenes.                 domain and clearly
                                                  separate validated classes
                                                  from experimental ones.

  False positives         Always issue an alert.  Confidence + persistence +
                                                  uncertainty state; alerts
                                                  require sustained
                                                  evidence.

  Slow inference          Process every frame.    Frame sampling,
                                                  lightweight model, GPU
                                                  acceleration where
                                                  available and bounded
                                                  dashboard refresh.

  Huge scope              Build a full disaster   One camera → one scene →
                          platform.               one vertical slice →
                                                  measurable scene
                                                  intelligence.
  --------------------------------------------------------------------------

# 8. The Dashboard Judges Should See

-   Large annotated emergency video with boxes, IDs, trajectories and
    zones.

-   CRITICAL / HIGH / MODERATE state plus a 0--100 prototype priority
    index.

-   People detected and unique tracked people.

-   People currently inside danger zones.

-   Hazard detections with confidence and persistence.

-   Exit A / Exit B: CLEAR, OCCUPIED or OBSTRUCTED based on configured
    zones.

-   Crowd density by zone.

-   Top 3 reasons for the current priority score.

-   Timeline showing whether the scene is improving or deteriorating.

-   An \'AI confidence / uncertainty\' indicator to demonstrate
    responsible deployment thinking.

# 9. The 60-Second Demo Script

1.  0--10 sec: Show ordinary emergency footage. RESQ detects people and
    scene hazards.

2.  10--20 sec: Persistent tracking appears. The system counts unique
    people and shows trajectories.

3.  20--30 sec: Several people enter a configured danger zone.
    People-at-risk rises.

4.  30--40 sec: A configured exit becomes occupied/obstructed. Exit
    status changes.

5.  40--50 sec: Temporal scene-state engine updates the priority index
    and displays the exact contributing factors.

6.  50--60 sec: RESQ highlights the highest-priority zone and states:
    \'Exit B currently obstructed; Exit A appears less obstructed in the
    camera view.\' Human responder remains in control.

# 10. What Makes This Technically Defensible

-   Computer vision is the actual perception engine.

-   Tracking creates temporal identity rather than independent frame
    detections.

-   Zone geometry creates scene-specific spatial reasoning.

-   Temporal aggregation turns noisy detections into stable events.

-   Risk is deterministic and explainable rather than an opaque
    AI-generated number.

-   Uncertainty is surfaced instead of hidden.

-   The system has explicit operating assumptions and failure
    boundaries.

# 11. Build Order

7.  Lock one emergency video and one scene configuration.

8.  Get YOLO inference running and save annotated output.

9.  Add tracking and stable IDs.

10. Implement polygon zones and occupancy calculations.

11. Implement danger-zone entry and dwell-time events.

12. Implement congestion/density metrics.

13. Implement exit obstruction state using predefined exit zones.

14. Implement temporal scene-state engine.

15. Implement explainable priority score.

16. Build dashboard around the already-working engine.

17. Record a deterministic fallback demo video in case live inference
    fails.

# 12. MVP Acceptance Criteria

-   The same person keeps a stable tracking ID across consecutive frames
    in the demo.

-   Danger-zone entry is detected from polygon overlap.

-   People-at-risk count changes when tracked people enter/leave the
    zone.

-   Crowd density changes with occupancy.

-   Exit status changes when configured obstruction conditions persist.

-   Priority score changes when measurable scene conditions change.

-   Every score can be explained by named contributing metrics.

-   The dashboard can show the annotated video and intelligence
    simultaneously.

-   The system can run the complete prerecorded demo without manual
    intervention.

-   If a detector is uncertain, RESQ displays uncertainty instead of
    fabricating certainty.

# 13. Judge Questions --- Strong Answers

**What is actually novel here?** Not object detection alone. RESQ
converts continuous emergency video into a temporal, spatial and
explainable scene state that prioritizes attention for a human
responder.

**Why not just YOLO + ByteTrack + OpenCV?** Those are the perception
primitives. The product layer is the scene-state engine: persistent
identities, zone events, temporal deterioration, explainable
prioritization and uncertainty handling.

**Can you guarantee the route is safe?** No. RESQ deliberately does not
make that claim. It reports camera-observed obstruction states for
predefined exits so a responder can make the final decision.

**How do you know 87/100 is correct?** It is not presented as a
universal truth. It is a transparent prototype priority index whose
components and thresholds are visible and reproducible.

**What happens if smoke is a false positive?** The system uses
confidence and temporal persistence and can surface an uncertain state
rather than immediately treating one frame as an emergency fact.

**Can this work on any CCTV?** The architecture is general, but the demo
is calibrated to a known camera/scene. Generalization requires
validation on additional environments.

**Why is tracking important?** It lets us reason about movement over
time: who entered a danger zone, how long they remained and whether
congestion is worsening.

**What happens if the model misses an object?** RESQ is decision
support, not an autonomous safety authority. The interface exposes
confidence and operating assumptions, and the system is evaluated on the
chosen scene before deployment.

# 14. Final Positioning

**RESQ is not an AI firefighter.** It is an explainable emergency video
intelligence layer. It watches the scene, maintains a structured
understanding of what is changing, quantifies measurable risk signals,
and puts the most important information in front of a human responder.

**Tagline:** SEE THE SCENE. UNDERSTAND THE CHANGE. PRIORITIZE THE
RESPONSE.

# 15. Team Execution Rule

Do not split the team into \'everyone build a feature\' mode. Split
around the dependency chain: perception → tracking → scene intelligence
→ interface → demo/integration. The first milestone is not a beautiful
dashboard. It is a working annotated video with stable detections.
Everything else builds on that.

**RESQ --- Hackathon MVP**\
A focused, measurable, explainable CV vertical slice.
