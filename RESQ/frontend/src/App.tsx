// RESQ Responder Dashboard (WORKFLOW.md Phase 13).
//
// Built around Incident State (intelligence/incident/state.py). The layout
// answers, top to bottom: what is happening, how severe, where, who is at
// risk, why it matters, what to do, and whether anyone was notified.
//
// Everything rendered here comes from real pipeline output. When data is
// missing the UI says so rather than showing a placeholder value.
//
// Two view modes (Task 2 — multi-camera): "single" is the original
// single-camera dashboard, now parameterized by whichever camera is
// selected; "grid" shows every configured camera at once plus a
// building-wide rollup. With exactly one camera configured (today's real
// state), the mode toggle and camera switcher don't render at all — the
// dashboard looks and behaves exactly as it always did.

import { useState } from "react";
import IncidentHeader from "./dashboard/IncidentHeader";
import ScenePanel from "./dashboard/ScenePanel";
import PeopleAtRiskPanel from "./dashboard/PeopleAtRiskPanel";
import AssessmentPanel from "./dashboard/AssessmentPanel";
import ExitsPanel from "./dashboard/ExitsPanel";
import NotificationPanel from "./dashboard/NotificationPanel";
import TimelinePanel from "./dashboard/TimelinePanel";
import CameraGrid from "./dashboard/CameraGrid";
import AggregateBar from "./dashboard/AggregateBar";
import SituationalView from "./floorplan/SituationalView";
import BuildingWideView from "./floorplan/BuildingWideView";
import Panel from "./components/Panel";
import { useIncidentState } from "./hooks/useIncidentState";
import { useBuildingConfig } from "./hooks/useBuildingConfig";
import { useCameras } from "./hooks/useCameras";
import { useAggregateIncident } from "./hooks/useAggregateIncident";
import { useAllCamerasBuildingConfig } from "./hooks/useAllCamerasBuildingConfig";

type ViewMode = "single" | "grid";
type BuildingScope = "camera" | "whole";

export default function App() {
  const { cameras } = useCameras();
  const [selectedCamera, setSelectedCamera] = useState("CAM-01");
  const [viewMode, setViewMode] = useState<ViewMode>("single");
  const [buildingScope, setBuildingScope] = useState<BuildingScope>("camera");

  // Derive the active camera ID instead of using an effect to sync it.
  // This avoids cascading renders and follows the "you might not need an effect" pattern.
  const activeCameraId = cameras.length > 0 && !cameras.some((c) => c.camera_id === selectedCamera)
    ? cameras[0].camera_id
    : selectedCamera;

  const { incident, loading, error } = useIncidentState(activeCameraId);
  const selectedCameraInfo = cameras.find((c) => c.camera_id === activeCameraId);
  const {
    zones,
    exits,
    imageWidth,
    imageHeight,
    loading: configLoading,
    error: configError,
  } = useBuildingConfig(activeCameraId, selectedCameraInfo?.resolution ?? undefined);
  const { aggregate } = useAggregateIncident();
  const { configs: allCameraConfigs } = useAllCamerasBuildingConfig(buildingScope === "whole" ? cameras : []);

  const connected = !error;
  const multiCamera = cameras.length > 1;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 antialiased">
      <IncidentHeader incident={incident} zones={zones} connected={connected} />

      <main className="mx-auto max-w-[1600px] px-6 py-5">
        {multiCamera && (
          <AggregateBar aggregate={aggregate} camerasConfigured={cameras.length} />
        )}

        {multiCamera && (
          <div className="mb-5 flex items-center gap-1 rounded-md border border-slate-800 bg-slate-900/40 p-0.5 w-fit">
            <ViewModeButton active={viewMode === "single"} onClick={() => setViewMode("single")}>
              Single camera
            </ViewModeButton>
            <ViewModeButton active={viewMode === "grid"} onClick={() => setViewMode("grid")}>
              All cameras
            </ViewModeButton>
          </div>
        )}

        {error && (
          <div
            className="mb-5 rounded-lg border border-amber-500/30 bg-amber-500/[0.07] px-4 py-3"
            role="alert"
          >
            <p className="text-sm font-semibold text-amber-300">
              Not receiving data from the RESQ backend
            </p>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-400">
              The dashboard is showing the last known state, which may be out of date. Confirm the
              backend is running:{" "}
              <code className="rounded bg-slate-800 px-1 py-0.5 font-mono text-2xs text-slate-300">
                uvicorn backend.main:app
              </code>
            </p>
          </div>
        )}

        {!error && !loading && !incident && (
          <div className="mb-5 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
            <p className="text-sm font-semibold text-slate-300">Standing by</p>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
              Connected to the backend, but no scene has been processed for {activeCameraId} yet.
              Start the pipeline with{" "}
              <code className="rounded bg-slate-800 px-1 py-0.5 font-mono text-2xs text-slate-400">
                RESQ_RUN_PIPELINE=true uvicorn backend.main:app
              </code>
            </p>
          </div>
        )}

        {loading && !incident && (
          <div className="mb-5 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
            <p className="text-sm text-slate-400">Connecting to scene…</p>
          </div>
        )}

        {viewMode === "grid" && multiCamera ? (
          <CameraGrid cameras={cameras} aggregate={aggregate} onSelectCamera={(id) => {
            setSelectedCamera(id);
            setViewMode("single");
          }} />
        ) : (
          <>
            {/* Row 1 — WHAT is happening (scene) and WHERE (situational view). */}
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <ScenePanel
                incident={incident}
                cameras={cameras}
                selectedCamera={activeCameraId}
                onSelectCamera={setSelectedCamera}
              />
              <Panel
                title="Building"
                subtitle={buildingScope === "whole" ? "Every configured camera's zones" : "Zones, exits and tracked positions"}
                action={
                  multiCamera ? (
                    <div className="flex items-center gap-1 rounded-md border border-slate-700 bg-slate-800/60 p-0.5">
                      <ScopeButton active={buildingScope === "camera"} onClick={() => setBuildingScope("camera")}>
                        This camera
                      </ScopeButton>
                      <ScopeButton active={buildingScope === "whole"} onClick={() => setBuildingScope("whole")}>
                        Whole building
                      </ScopeButton>
                    </div>
                  ) : undefined
                }
                bodyClassName="p-4"
              >
                <div className="h-[420px]">
                  {buildingScope === "whole" && multiCamera ? (
                    <BuildingWideView
                      cameraConfigs={allCameraConfigs}
                      aggregate={aggregate}
                      selectedCameraId={selectedCamera}
                      onSelectCamera={setSelectedCamera}
                    />
                  ) : (
                    <SituationalView
                      incident={incident}
                      zones={zones}
                      exits={exits}
                      imageWidth={imageWidth}
                      imageHeight={imageHeight}
                      configError={configError}
                      configLoading={configLoading}
                    />
                  )}
                </div>
              </Panel>
            </div>

            {/* Row 2 — WHO is at risk, WHY it matters, exits. */}
            <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-3">
              <PeopleAtRiskPanel incident={incident} zones={zones} />
              <AssessmentPanel incident={incident} zones={zones} />
              <div className="flex flex-col gap-5">
                <ExitsPanel incident={incident} exits={exits} />
                <NotificationPanel incident={incident} />
              </div>
            </div>

            {/* Row 3 — WHAT CHANGED. */}
            <div className="mt-5">
              <TimelinePanel incident={incident} />
            </div>
          </>
        )}

        <footer className="mt-6 border-t border-slate-800 pt-4 pb-2">
          <p className="text-2xs leading-relaxed text-slate-600">
            RESQ converts emergency video into structured, explainable scene intelligence. It is
            decision support, not an autonomous emergency-response system: it does not dispatch
            responders, diagnose injuries, claim exact real-world distance, or guarantee evacuation
            routes. Only configured zones, exits and contacts are evaluated.
          </p>
        </footer>
      </main>
    </div>
  );
}

function ScopeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded px-2.5 py-1 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
        active ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

function ViewModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
        active ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}
