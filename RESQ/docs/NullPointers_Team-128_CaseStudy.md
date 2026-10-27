RESQ

Real-Time Emergency Scene Intelligence using Computer Vision

Case Study --- Building-Aware Emergency Scene Intelligence

Team: NULL POINTERS

Team Members: SIRI SINGU · YUVA YASHWANTH · ANVITH SAI · SRI HARSHA ·
SATHWIKA

Hackathon: LAUNCHPADX HACKATHON

Track: Computer Vision

SEE THE SCENE. UNDERSTAND THE CHANGE. PRIORITIZE THE RESPONSE.

⸻

1\. Executive Summary

Emergencies inside buildings create an information problem before they
become a response problem.

Modern buildings may already have multiple CCTV cameras, but
conventional surveillance systems primarily provide video streams.
During an emergency, responders still need to interpret those streams
manually, determine where people are located, identify hazards,
recognize congestion, understand which areas are becoming dangerous, and
assess whether known exits appear usable.

RESQ was designed to close this gap.

RESQ is a building-specific, explainable emergency intelligence layer
that combines:

\* Computer vision

\* Persistent object tracking

\* Building floor plans

\* Configured camera zones

\* Temporal scene analysis

\* Historical scene baselines

\* Explainable prioritization

The key idea is simple:

CCTV shows what is happening. RESQ explains what is changing and where
responders should look first.

The system does not attempt to replace emergency responders or
autonomously control evacuation. Instead, it converts raw camera
observations into a structured, continuously updated building scene
state that keeps the human responder in control.

⸻

2\. The Problem Before RESQ

2.1 The Existing Environment

Consider a typical college, hospital, office, mall, warehouse, or public
building.

The building may contain:

\* Multiple CCTV cameras

\* Several floors

\* Corridors

\* Staircases

\* Emergency exits

\* Restricted areas

\* High-occupancy zones

\* Fire safety infrastructure

During normal operation, monitoring CCTV footage is relatively
straightforward.

During an emergency, the situation changes rapidly.

A responder may suddenly need to answer:

1\. How many people are currently visible?

2\. Where are they located?

3\. Are people entering a dangerous area?

4\. Is a particular corridor becoming crowded?

5\. Has a known exit become occupied or obstructed?

6\. Is a hazard persisting or was it only a single-frame detection?

7\. Is the situation improving or deteriorating?

8\. Which area deserves attention first?

9\. How confident is the system?

10\. Which information is actually known versus unknown?

Traditional CCTV does not directly answer these questions.

It gives the responder pixels.

The responder must create the understanding.

⸻

3\. Why This Problem Matters

Disasters create large-scale human and infrastructure consequences.
According to the United Nations Office for Disaster Risk Reduction, more
than 123 million people were affected by disasters on average each year
during 2015--2024, while reported direct economic losses exceeded
US\$1.1 trillion over the same period. (UNDRR)

Fire emergencies alone demonstrate the frequency of emergency incidents.
The U.S. National Fire Protection Association estimated that local fire
departments responded to approximately 1.38 million fires in 2024, with
3,920 civilian fire deaths and 11,780 reported civilian injuries. (NFPA)

The challenge is not simply generating more video.

NIST notes that public-safety responders can benefit from real-time
analysis of video from surveillance cameras and other sources, with the
goal of creating a temporal and spatial visualization of an event as it
unfolds. (NIST)

NIST also identifies a practical monitoring problem: the number of video
streams can exceed the number of people available to manually monitor
them. (NIST)

The fundamental gap

Existing CCTV RESQ

Displays video Interprets video

Frame-by-frame observation Persistent scene state

Manual counting Automated tracking

Raw bounding boxes Building-zone context

Individual detections Temporal events

No understanding of building layout Configured building model

Manual prioritization Explainable Priority Index

Uncertain information often hidden Unknown/uncertain states explicitly
shown

Responder watches everything Responder sees what changed

⸻

4\. The Central Insight

The original problem could have been approached as:

"Build an AI system that detects emergencies in CCTV footage."

That sounds impressive, but it is technically weak.

A detector alone does not understand a building.

Instead, RESQ asks:

"Given a known building and its camera locations, what has changed in
the emergency scene, where is it changing, and what information should a
human responder inspect first?"

This changes the entire architecture.

RESQ does not attempt to discover the building layout from CCTV.

The building is configured beforehand.

The system knows:

\* Floors

\* Rooms

\* Corridors

\* Stairways

\* Exits

\* Safe zones

\* Restricted areas

\* Camera positions

\* Camera viewing zones

\* Zone connectivity

Computer vision then observes what is happening inside that known
environment.

⸻

5\. Before RESQ: The Existing Workflow

Step 1 --- Camera footage is generated

CCTV cameras continuously produce video.

Step 2 --- A responder/operator watches the feeds

The operator manually scans available camera views.

Step 3 --- People are visually identified

The responder estimates:

\* Number of people

\* Approximate locations

\* Movement

\* Crowding

Step 4 --- Hazards are manually noticed

The operator attempts to identify:

\* Fire

\* Smoke

\* Obstacles

\* Other configured hazards

Step 5 --- The operator interprets the building context

The responder must remember:

\* Which camera covers which area

\* Where exits are

\* Which corridors connect

\* Which areas are dangerous

Step 6 --- The responder compares what is happening over time

They must mentally determine whether:

\* Occupancy is increasing

\* Congestion is worsening

\* A hazard is persistent

\* An exit is becoming blocked

Step 7 --- The responder prioritizes manually

Finally, the operator decides:

"Which area should I look at first?"

This is where cognitive load becomes a major problem.

⸻

6\. The Limitations of the Existing Approach

Limitation 1 --- Video contains information, not intelligence

A camera can show a person.

It does not automatically explain:

"12 tracked people have entered the configured danger zone."

⸻

Limitation 2 --- Single-frame detection is insufficient

A single detection may be:

\* A false positive

\* Temporary

\* Caused by occlusion

\* Caused by visual noise

\* An object that disappears immediately

Emergency intelligence needs persistence over time.

⸻

Limitation 3 --- Generic computer vision lacks spatial context

A model can detect a door.

It cannot safely assume:

"This is Emergency Exit B."

RESQ therefore explicitly configures emergency exits instead of
inferring them from appearance.

⸻

Limitation 4 --- Pixel proximity is not physical distance

Two objects being close in an image does not necessarily mean they are
physically close.

RESQ therefore uses configured image-space zones for the MVP rather than
making unsupported real-world distance claims.

⸻

Limitation 5 --- Raw detections do not show deterioration

Knowing:

"20 people detected"

is less useful than knowing:

"Zone C occupancy has increased continuously over the last 30 seconds
and is now above its configured threshold."

That requires temporal reasoning.

⸻

7\. RESQ --- Proposed Solution

RESQ transforms emergency video into structured building intelligence.

Core pipeline

EMERGENCY VIDEO

│

▼

Frame Preprocessing

│

▼

YOLO Detector

│

┌────────┴────────┐

▼ ▼

Bounding Boxes Class Labels

│ │

└────────┬────────┘

▼

Object Tracking

│

▼

Persistent Track IDs

│

▼

Building Zone Engine

│

▼

Temporal Scene Engine

│

┌─────────┴─────────┐

▼ ▼

Current State Historical Baseline

│ │

└─────────┬─────────┘

▼

Explainable Risk /

Priority Engine

│

▼

RESQ Dashboard

The architecture follows the PRD's defined chain:

video ingestion → detection → tracking → zone engine → building model →
temporal scene state → historical baseline → explainable priority engine
→ responder dashboard.

⸻

8\. Building Digital Twin

One of RESQ's most important features is the Building Digital Twin.

This is not a 3D simulation.

It is a structured representation of the building's relevant spatial
information.

Static building information

BUILDING

│

├── Floor 1

│ ├── Room A

│ ├── Corridor A

│ ├── Staircase A

│ ├── Exit A

│ └── Danger Zone A

│

└── Camera Registry

├── Camera 01

├── Camera 02

└── Camera 03

The building model stores:

\* Building identity

\* Floors

\* Zones

\* Rooms

\* Corridors

\* Exits

\* Stairs

\* Restricted zones

\* Safe zones

\* Camera positions

\* Camera orientation

\* Camera-covered zones

\* Zone connectivity

This allows RESQ to understand the meaning of visual observations within
a known environment.

⸻

9\. Dynamic Emergency Scene State

The second layer is dynamic.

It represents what is happening right now.

Dynamic information

\* People

\* Persistent tracking IDs

\* Movement trajectories

\* Zone occupancy

\* Danger-zone occupancy

\* Crowd density

\* Hazard confidence

\* Hazard persistence

\* Obstruction persistence

\* Temporal changes

\* Priority

\* Confidence

\* Uncertainty

Therefore:

Building Digital Twin = What the building is.

Emergency Scene State = What is happening inside it.

This two-layer architecture is the foundation of RESQ.

⸻

10\. Core Computer Vision Features

10.1 Person Detection

The detector identifies people within the camera frame.

Output:

Class: Person

Bounding Box: x1, y1, x2, y2

Confidence: 0.94

⸻

10.2 Persistent Tracking

Detection alone treats every frame as independent.

Tracking gives the system continuity.

Example:

Frame 1 → Person #17

Frame 2 → Person #17

Frame 3 → Person #17

Frame 4 → Person #17

This allows RESQ to calculate:

\* Dwell time

\* Entry

\* Exit

\* Movement

\* Occupancy

\* Congestion trends

\* Zone transitions

The PRD specifically identifies tracking as the mechanism that powers
dwell time, zone entry, congestion trends, movement direction and
temporal events.

⸻

11\. Configured Danger Zones

A responder or administrator defines a polygon representing a dangerous
area.

Example:

Camera View

┌───────────────────────────────┐

│ │

│ 👤 #01 │

│ │

│ ┌──────────────┐ │

│ 👤 │ DANGER ZONE │ │

│ #02 │ │ │

│ └──────────────┘ │

│ │

└───────────────────────────────┘

When a tracked person enters the configured polygon:

Person #02

↓

Danger Zone Entry

↓

People-at-Risk Count +1

↓

Priority Contributors Updated

This is more defensible than claiming the model knows the exact physical
distance between a person and a hazard.

⸻

12\. Hazard Detection

RESQ can support validated hazard classes.

Potential examples include:

\* Fire

\* Smoke

\* Other validated scene-specific hazards

However, the system does not automatically activate every hazard
detector.

A hazard class must be validated against the selected scene.

This prevents the system from presenting unreliable detections as facts.

The PRD explicitly states that smoke/fire should only be enabled when
validated for the selected footage.

⸻

13\. Temporal Reasoning

This is where RESQ becomes more than an object detector.

Instead of asking:

"What is visible in this frame?"

RESQ asks:

"What has changed over time?"

Example

At 10:00:00:

Zone A occupancy = 3

At 10:00:10:

Zone A occupancy = 7

At 10:00:20:

Zone A occupancy = 12

RESQ can identify:

Occupancy increasing

rather than merely displaying three unrelated counts.

The system can reason about:

\* Entry

\* Exit

\* Dwell time

\* Increasing occupancy

\* Congestion

\* Persistent hazards

\* Persistent obstruction

\* Scene deterioration

⸻

14\. Historical Baseline

Emergency intelligence becomes stronger when the system understands
normal behavior.

RESQ can maintain baseline statistics for:

\* Normal occupancy

\* Typical movement

\* Typical zone usage

\* Camera health

\* Time-window behavior

For example:

Normal occupancy:

Zone A → 5--10 people

Current occupancy:

Zone A → 27 people

Deviation:

HIGH

The important distinction is that RESQ does not continuously retrain
YOLO on raw CCTV.

Instead, daily footage can contribute to scene statistics and baselines,
while new model training uses controlled, labeled datasets and offline
validation.

⸻

15\. Exit Intelligence

RESQ does not claim:

"This route is definitely safe."

Instead, it observes explicitly configured exits.

Possible states:

CLEAR

No persistent obstruction observed.

OCCUPIED

People are occupying the configured exit area.

OBSTRUCTED

Persistent visual evidence suggests obstruction.

UNCERTAIN

The available evidence is insufficient.

This distinction is critical.

If a route segment is not visible to a camera, RESQ marks it UNKNOWN
instead of assuming it is clear.

⸻

16\. Explainable Priority Index

Instead of producing a mysterious AI score, RESQ uses a deterministic
prototype Priority Index.

Example:

Priority =

0.40 × Hazard Exposure

\+ 0.25 × People in Danger Zones

\+ 0.20 × Congestion

\+ 0.15 × Exit Obstruction

The result is normalized to:

0 ─────────────────────────── 100

LOW CRITICAL

The dashboard also displays the contributors.

Example:

PRIORITY: 82 / 100

Top Contributors:

🔥 Hazard Exposure +32

👥 Danger Zone Occupancy +24

🚧 Exit Obstruction +16

Trend:

↑ DETERIORATING

This makes the output explainable rather than presenting an unexplained
"AI risk score."

⸻

17\. What RESQ Actually Detects

Signal Source Output

People Detector + tracker Current/unique tracked people

Hazard Validated detector + persistence Presence/confidence/persistence

Danger-zone occupancy Track IDs + polygons People inside danger zones

Crowding Zone occupancy + temporal baseline Density/occupancy state

Exit state Configured exit polygon + persistence Clear / Occupied /
Obstructed / Uncertain

Scene deterioration Time-series metrics Increasing / Decreasing / Stable

Priority Weighted deterministic signals 0--100 prototype index

⸻

18\. RESQ Dashboard

The dashboard is not simply a place to display YOLO bounding boxes.

It combines visual evidence + building context + temporal intelligence.

Main dashboard components

1\. Live / prerecorded video

Displays:

\* Bounding boxes

\* Class labels

\* Track IDs

\* Trajectories

\* Configured zones

2\. Building floor plan

Displays:

\* Cameras

\* Affected zones

\* Exits

\* Building context

3\. Emergency priority

CRITICAL

82 / 100

4\. People statistics

Detected: 17

Unique tracked: 14

Danger zone: 6

5\. Hazard panel

Smoke

Confidence: 91%

Persistence: 8.2 sec

6\. Exit status

Exit A → CLEAR

Exit B → OBSTRUCTED

Exit C → UNCERTAIN

7\. Scene timeline

10:02:10 STABLE

10:02:20 OCCUPANCY ↑

10:02:30 DANGER-ZONE ENTRY

10:02:40 EXIT B OBSTRUCTION

10:02:50 DETERIORATING

8\. Explainability

WHY PRIORITY IS HIGH

1\. 6 people in danger zone

2\. Exit B obstruction persists

3\. Zone occupancy increasing

9\. Uncertainty

AI Confidence: 87%

Unobserved Area: UNKNOWN

These dashboard requirements are directly aligned with the RESQ PRD.

⸻

19\. Before vs After Implementation

BEFORE RESQ

CCTV

│

▼

Raw Video Feeds

│

▼

Human Operator

│

┌──────────┼──────────┐

▼ ▼ ▼

Count Identify Interpret

People Hazards Building

│ │ │

└──────────┼──────────┘

▼

Manual Assessment

│

▼

Manual Prioritization

Problems

\* High cognitive load

\* Manual counting

\* Manual hazard observation

\* Difficult temporal comparison

\* No persistent identity

\* No structured building context

\* No automatic zone occupancy

\* No explainable priority

\* Unknown conditions may be overlooked

⸻

20\. AFTER RESQ

CCTV

│

▼

RESQ PERCEPTION

│

▼

Persistent Tracking

│

▼

Building Zone Mapping

│

▼

Temporal Scene Analysis

│

▼

Historical Baseline

│

▼

Explainable Priority Engine

│

▼

RESQ COMMAND VIEW

The responder now receives:

┌───────────────────────────────────────┐

│ RESQ INCIDENT VIEW │

├───────────────────────────────────────┤

│ │

│ VIDEO BUILDING MAP │

│ 👤 #01 EXIT A 🟢 │

│ 👤 #02 EXIT B 🔴 │

│ 👤 #03 ZONE C ⚠️ │

│ │

├───────────────────────────────────────┤

│ PRIORITY: 82 / 100 │

│ │

│ TOP REASONS │

│ • 6 people in danger zone │

│ • Exit B obstruction persists │

│ • Occupancy increasing │

│ │

│ TREND: DETERIORATING │

│ CONFIDENCE: 87% │

│ │

│ HUMAN RESPONDER DECISION REQUIRED │

└───────────────────────────────────────┘

⸻

21\. The Transformation

The most important transformation can be summarized as:

Before After

Raw video Structured scene state

Objects Persistent entities

Frames Temporal events

Camera view Building-aware view

Manual zone interpretation Configured zone intelligence

Manual counting Automated occupancy

Single detections Persistent evidence

Hidden uncertainty Explicit uncertainty

Raw observations Explainable priority

Watch everything Inspect what changed

CCTV system Responder intelligence layer

⸻

22\. Technical Architecture

End-to-End Architecture

┌──────────────────────────┐

│ VIDEO SOURCE │

│ CCTV / Recorded Video │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ VIDEO INGESTION │

│ Frame sampling │

│ Resolution handling │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ CV DETECTOR │

│ YOLO / Validated Models │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ TRACKER │

│ ByteTrack / Compatible │

│ Persistent IDs │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ ZONE ENGINE │

│ OpenCV polygons │

│ Zone membership │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ BUILDING MODEL │

│ Floors / zones / exits │

│ Cameras / connectivity │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ TEMPORAL SCENE ENGINE │

│ Occupancy / dwell / │

│ congestion / persistence │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ HISTORICAL BASELINE │

│ Normal scene behavior │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ EXPLAINABLE PRIORITY │

│ Score + contributors │

│ + uncertainty │

└────────────┬─────────────┘

│

▼

┌──────────────────────────┐

│ RESQ DASHBOARD │

│ Video + map + alerts │

│ Timeline + metrics │

└──────────────────────────┘

This architecture is based on the component chain defined in the PRD.

⸻

23\. Why YOLO?

YOLO is used as a perception primitive, not as the entire intelligence
layer.

Its role is to identify visual entities in frames.

The output can then be consumed by:

YOLO

↓

Bounding Boxes

↓

Tracking

↓

Zone Membership

↓

Temporal Events

↓

Priority

Therefore, the technical novelty does not depend on claiming that YOLO
itself is innovative.

The innovation is the structured fusion of:

\* Detection

\* Tracking

\* Building model

\* Configured camera zones

\* Temporal events

\* Historical baselines

\* Uncertainty

\* Explainable prioritization

That is the precise novelty claim defined by the RESQ architecture.

⸻

24\. Why Tracking?

Without tracking:

Frame 1 → Person

Frame 2 → Person

Frame 3 → Person

The system cannot confidently determine whether these are the same
person.

With tracking:

Frame 1 → Person #17

Frame 2 → Person #17

Frame 3 → Person #17

Now the system can derive:

\* Movement

\* Dwell time

\* Entry

\* Exit

\* Direction

\* Zone transitions

\* Persistent occupancy

\* Congestion trends

Tracking therefore transforms detections into events.

⸻

25\. Why Building Configuration?

A generic AI system might see:

Door

Person

Corridor

RESQ sees:

Person #17

↓

Corridor C

↓

Danger Zone D

↓

Exit B nearby in configured building graph

This is the difference between object recognition and environment-aware
intelligence.

The blueprint is therefore not training data for YOLO.

It is a spatial configuration layer that tells the system what visual
observations mean within the building.

⸻

26\. Building Onboarding Process

Before RESQ can operate in a building:

Step 1

Upload the floor plan or structured building map.

Step 2

Define:

\* Floors

\* Rooms

\* Corridors

\* Stairs

\* Elevators

\* Exits

\* Safe zones

\* Restricted areas

Step 3

Register cameras.

Each camera receives:

\* Camera ID

\* Floor

\* Approximate position

\* Orientation

\* Covered zones

Step 4

Draw image-space polygons.

These define which parts of the camera frame correspond to important
building zones.

Step 5

Map camera zones to building zones.

Step 6

Explicitly define emergency exits.

Step 7

Define valid zone connectivity.

Step 8

Configure thresholds.

Step 9

Calibrate against normal footage.

This means RESQ is configured once and then used repeatedly, rather than
trying to rediscover the building every time.

⸻

27\. Data Model

RESQ maintains structured incident information.

Building

building_id

name

floors

blueprint_version

Zone

zone_id

floor

type

polygon/map geometry

connected zones

priority metadata

Exit

exit_id

floor

map location

camera-visible zones

status rules

Camera

camera_id

building_id

floor

position

orientation

stream/source

calibration metadata

Observation

timestamp

camera_id

class

confidence

bounding box

track_id

Zone Event

entry

exit

dwell

occupancy

obstruction

hazard

timestamp

confidence

Incident State

current priority

contributors

uncertainty

affected zones

timeline

The PRD defines these entities as the core RESQ data model.

⸻

28\. A Complete Emergency Scenario

Scenario

A fire/emergency scenario occurs inside a building.

The building has:

\* Camera 01 covering Corridor A

\* Camera 02 covering Corridor B

\* Exit A

\* Exit B

\* Danger Zone D

⸻

T = 0 seconds

Normal scene.

People: 5

Danger Zone: 0

Exit A: CLEAR

Exit B: CLEAR

Priority: 12

Trend: STABLE

⸻

T = 10 seconds

Additional people enter Corridor A.

People: 9

Danger Zone: 2

Exit A: CLEAR

Exit B: CLEAR

Priority: 34

Trend: INCREASING

RESQ identifies increasing occupancy.

⸻

T = 20 seconds

People enter the configured danger zone.

Danger Zone Occupancy: 5

The system increases the corresponding priority contributor.

⸻

T = 30 seconds

Persistent obstruction appears around Exit B.

Exit B:

OBSTRUCTED

The system does not change the status based on a single frame.

It waits for persistent evidence.

⸻

T = 40 seconds

Historical comparison indicates that occupancy is significantly above
the normal baseline.

Zone A:

NORMAL → HIGH

⸻

T = 50 seconds

The Priority Index becomes:

82 / 100

CRITICAL

The dashboard explains:

WHY?

1\. 6 people currently in danger zone

2\. Exit B obstruction persists

3\. Occupancy increasing above baseline

⸻

T = 60 seconds

RESQ presents the responder with:

Highest Priority: Zone D

Exit B: Observed obstruction

Exit A: Less obstructed in monitored view

Confidence: 87%

Human responder decision required

This is the exact type of end-to-end demonstration specified in the
hackathon demo flow.

⸻

29\. After Implementation: What Changes for the Responder?

The responder no longer needs to mentally combine every individual
observation.

Instead of:

"I see several people... there's something happening near the
corridor... I think Exit B may be blocked..."

RESQ provides:

Zone D is currently the highest-priority monitored area because
occupancy is increasing, 6 tracked people are inside the configured
danger zone, and Exit B has persistent observed obstruction.

The responder still makes the decision.

RESQ provides the evidence.

⸻

30\. Human-in-the-Loop Design

RESQ deliberately does not become an autonomous emergency commander.

The system can say:

Exit B

Observed obstruction

Confidence: 89%

It should not say:

EXIT B IS SAFE / UNSAFE

unless the system has sufficient validated evidence and calibration to
make such a claim.

Likewise, RESQ does not issue autonomous evacuation commands.

The human responder remains responsible for final emergency decisions.

⸻

31\. Responsible AI Boundaries

RESQ explicitly avoids several dangerous claims.

RESQ does NOT:

\* Diagnose injuries

\* Detect medical conditions

\* Automatically generate floor plans

\* Assume every door is an emergency exit

\* Convert pixel distance into real-world distance without calibration

\* Guarantee evacuation routes

\* Claim universal performance across disasters

\* Continuously retrain itself on raw CCTV

\* Autonomously command evacuation

\* Treat uncertain information as truth

Instead:

UNKNOWN is a valid output.

That is an important safety feature, not a weakness.

⸻

32\. Hackathon MVP

The implementation is intentionally constrained.

MVP includes

\* One building

\* One floor if required

\* One or two fixed camera views

\* One emergency scenario

\* Person detection

\* Stable tracking

\* At least one validated hazard class

\* Configured danger zones

\* Configured exits

\* Temporal congestion

\* Obstruction state

\* Building floor-plan visualization

\* Explainable Priority Index

\* Complete prerecorded demonstration

⸻

33\. What Was Intentionally NOT Built

RESQ avoids scope explosion.

The MVP does not attempt to build:

\* A city-wide disaster command center

\* Autonomous drone dispatch

\* Robot dispatch

\* Automatic emergency-service communication

\* Universal CCTV compatibility

\* Medical triage

\* Automatic blueprint generation

\* Uncontrolled online retraining

\* Guaranteed evacuation routing

\* A universal multi-disaster model

This constraint is important.

It makes the project demonstrable, defensible and technically credible.

⸻

34\. Acceptance Criteria

A successful RESQ implementation should demonstrate:

Vision

\* Stable person detection

\* Stable tracking IDs

\* Confidence values

Spatial intelligence

\* Building zones loaded

\* Camera polygons mapped

\* Danger-zone membership detected

Temporal intelligence

\* Entry/exit events

\* Occupancy changes

\* Persistent hazards

\* Persistent obstruction

\* Scene deterioration

Decision support

\* Priority Index changes when conditions change

\* Contributors are displayed

\* Uncertainty is visible

\* Historical baseline can be shown

Visualization

\* Video and floor plan appear together

\* Affected zones are visible

\* Exit states are visible

\* Timeline is available

Demonstration

\* Full scenario runs end-to-end

\* No manual intervention is required during the demo

These correspond directly to the PRD's acceptance criteria.

⸻

35\. Measuring Success

The case study should not claim arbitrary production-level accuracy
unless the team actually measures it.

Instead, evaluate RESQ across several dimensions.

Computer Vision Metrics

Detection

\* Precision

\* Recall

\* mAP

\* Confidence distribution

Tracking

\* ID stability

\* ID switches

\* Track persistence

⸻

Scene Intelligence Metrics

Zone Detection

\* Correct zone entry

\* Correct zone exit

\* Occupancy accuracy

Hazard Intelligence

\* Detection precision

\* Detection recall

\* Persistence accuracy

Exit State

\* Correct CLEAR/OBSTRUCTED classification

\* False obstruction rate

⸻

System Metrics

\* FPS

\* End-to-end latency

\* Dashboard refresh rate

\* Camera processing capacity

\* CPU/GPU utilization

⸻

Explainability Metrics

For every Priority Index state:

Score

\+

Top contributors

\+

Confidence

\+

Uncertainty

\+

Affected zone

The system should be able to explain why the priority changed.

⸻

36\. Before-and-After User Experience

Before

Responder sees:

CAM 01

CAM 02

CAM 03

CAM 04

CAM 05

CAM 06

The responder must inspect everything.

⸻

After

Responder sees:

CURRENT INCIDENT

Priority: 82 / 100

Trend: DETERIORATING

Highest Priority:

Zone D

Why?

• 6 people in danger zone

• Exit B obstruction

• Occupancy increasing

Exit A:

Less obstructed in monitored area

Exit B:

Persistent observed obstruction

Uncertainty:

Camera coverage incomplete

Decision:

Human responder required

The goal is not to remove the responder.

The goal is to make the responder faster and better informed.

⸻

37\. Why RESQ Is Different

A judge could reasonably ask:

"Why isn't this just YOLO + ByteTrack + OpenCV?"

The answer:

YOLO detects objects.

ByteTrack maintains identities.

OpenCV can process image-space geometry.

But those components individually do not maintain a building-specific
temporal incident state.

RESQ combines them with:

Known Building

\+

Camera Context

\+

Object Detection

\+

Persistent Tracking

\+

Zone Membership

\+

Temporal Events

\+

Historical Baseline

\+

Uncertainty

\+

Explainable Priority

↓

BUILDING-AWARE INCIDENT STATE

That is the product.

The PRD explicitly frames this as the difference between tools that
produce observations and RESQ maintaining a building-specific state of
the incident.

⸻

38\. Deployment Evolution

Phase 1 --- Hackathon

1 Building

1 Incident

1--2 Cameras

Deterministic Scene Intelligence

Phase 2 --- Building Deployment

Multiple Cameras

Multiple Floors

Camera Health

Calibration

Privacy Controls

Access Control

Phase 3 --- Learning Layer

Validated Hard Examples

Offline Model Improvement

Building Baselines

Shadow Deployment

Phase 4 --- Campus

Building A ─┐

Building B ─┼── Central Responder Console

Building C ─┘

Phase 5 --- Multi-Site

Reusable Building Onboarding

GIS / BIM Integration

Incident APIs

Rigorous Validation

The roadmap deliberately delays broad operational claims until
substantial validation exists.

⸻

39\. Expected Impact

If successfully implemented, RESQ changes emergency monitoring from:

"Watch the cameras."

to:

"Understand the scene."

From:

"Something is happening."

to:

"This zone is deteriorating."

From:

"There are people here."

to:

"Six tracked people are currently inside the configured danger zone."

From:

"That exit looks blocked."

to:

"Exit B has persistent observed obstruction in the monitored camera
area."

From:

"AI says danger = 82."

to:

"Priority = 82 because hazard exposure, danger-zone occupancy and exit
obstruction are the dominant contributors."

⸻

40\. The Final Product Positioning

RESQ is not an AI firefighter.

It is the intelligence layer between:

BUILDING CAMERAS

↓

RESQ

↓

HUMAN RESPONDERS

The building blueprint provides trusted spatial context.

Computer vision observes the changing scene.

Tracking provides persistent identity.

Temporal reasoning detects change.

Historical data defines normal behavior.

The explainable Priority Engine tells responders:

What changed.

Where it changed.

Why it matters.

How certain the system is.

And most importantly:

What the responder should inspect first.

s

41\. Final Case Study Summary

Before RESQ

Emergency footage existed, but actionable understanding depended heavily
on manual monitoring and human interpretation.

RESQ Implementation

The system introduced:

\* Building-aware spatial context

\* Computer vision detection

\* Persistent tracking

\* Configured danger zones

\* Hazard persistence

\* Temporal scene analysis

\* Historical baselines

\* Exit-state monitoring

\* Explainable Priority Index

\* Uncertainty handling

\* Integrated responder dashboard

After RESQ

The same camera footage becomes a structured emergency scene state.

Instead of forcing responders to interpret every frame independently,
RESQ continuously summarizes:

WHO?

↓

WHAT?

↓

WHERE?

↓

WHAT CHANGED?

↓

IS IT GETTING WORSE?

↓

WHAT INFORMATION MATTERS MOST?

↓

HOW CERTAIN ARE WE?

The system therefore moves CCTV from passive observation toward
building-aware situational intelligence, while keeping the final
emergency decision with the human responder.

42\. One-Line Value Proposition

RESQ converts emergency camera footage into a building-aware, temporal
and explainable incident state so human responders can understand what
is changing, where attention is needed, and which monitored exits or
zones appear most relevant.

43\. Closing Statement

SEE THE SCENE.

UNDERSTAND THE CHANGE.

PRIORITIZE THE RESPONSE.
