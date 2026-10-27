import { useMemo } from "react";
import type { CameraBuildingConfig } from "../hooks/useAllCamerasBuildingConfig";
import type { AggregateIncident } from "../types/aggregate";
import { zoneFillColor, zoneStrokeColor } from "../lib/theme";
import { type Camera, type Vec3, centroid, imageToGround, project, toPointsAttr } from "./scene3d";

interface Props {
  cameraConfigs: CameraBuildingConfig[];
  aggregate: AggregateIncident | null;
  selectedCameraId: string;
  onSelectCamera: (cameraId: string) => void;
}

const VIEW_W = 900;
const VIEW_H = 360;
const POD_WIDTH = 300; // world units each camera's own zone footprint is normalized into
const POD_GAP = 90;
const FIXED_CAMERA: Camera = { yaw: -0.5, pitch: 0.95, zoom: 0.62 };

/**
 * Whole-building overview (Task 4.2): every configured camera's zone
 * footprint laid out side by side, each independently calibrated against
 * its own resolution (Task 4.3) — RESQ does not claim cameras share one
 * real-world coordinate system, so this is honestly a row of separate
 * camera "pods," not a single fused floor plan. The currently-selected
 * camera is highlighted; clicking any pod selects that camera and can
 * hand off to the detailed single-camera 3D view.
 *
 * Deliberately flatter/simpler than the single-camera SituationalView
 * (no extruded walls, fixed camera angle) — an overview of N cameras
 * needs to stay legible, not show N full detailed scenes at once.
 */
export default function BuildingWideView({ cameraConfigs, aggregate, selectedCameraId, onSelectCamera }: Props) {
  const summaryByCameraId = new Map((aggregate?.cameras ?? []).map((c) => [c.camera_id, c]));

  const pods = useMemo(() => {
    return cameraConfigs.map((cfg, index) => {
      const points = [...cfg.zones.flatMap((z) => z.polygon), ...cfg.exits.flatMap((e) => e.polygon)];
      const hasGeometry = points.length > 0;

      // Each camera's own polygons are normalized into a POD_WIDTH-wide
      // footprint using *that camera's own* imageToGround calibration —
      // never another camera's resolution or scale.
      const toGround = (px: number, py: number): Vec3 =>
        imageToGround(px, py, cfg.imageWidth, cfg.imageHeight, POD_WIDTH);

      const offsetX = index * (POD_WIDTH + POD_GAP) + POD_WIDTH / 2;

      const zoneShapes = cfg.zones.map((zone) => {
        const ground = zone.polygon.map(([px, py]) => {
          const g = toGround(px, py);
          return { ...g, x: g.x + offsetX };
        });
        return { zone, ground, groundCentroid: centroid(ground) };
      });

      return { cfg, offsetX, hasGeometry, zoneShapes };
    });
  }, [cameraConfigs]);

  const totalWidth = pods.length > 0 ? pods[pods.length - 1].offsetX + POD_WIDTH / 2 : POD_WIDTH;
  const recenter = totalWidth / 2;

  const p = (v: Vec3) => project({ ...v, x: v.x - recenter }, FIXED_CAMERA, VIEW_W, VIEW_H);

  return (
    <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="h-full w-full">
      {pods.map(({ cfg, hasGeometry, zoneShapes }) => {
        const isSelected = cfg.camera.camera_id === selectedCameraId;
        const summary = summaryByCameraId.get(cfg.camera.camera_id);
        const podCenter = zoneShapes.length > 0 ? centroid(zoneShapes.map((z) => z.groundCentroid)) : { x: 0, y: 0, z: 0 };
        const labelPos = p(podCenter);

        return (
          <g
            key={cfg.camera.camera_id}
            onClick={() => onSelectCamera(cfg.camera.camera_id)}
            className="cursor-pointer"
            opacity={isSelected ? 1 : 0.55}
          >
            {hasGeometry ? (
              zoneShapes.map(({ zone, ground, groundCentroid }) => {
                const proj = ground.map(p);
                const projCenter = p(groundCentroid);
                return (
                  <g key={zone.id}>
                    <polygon
                      points={toPointsAttr(proj)}
                      fill={zoneFillColor[zone.type]}
                      stroke={zoneStrokeColor[zone.type]}
                      strokeWidth={isSelected ? 2 : 1}
                    />
                    {summary && (summary.people_count > 0 || summary.hazard_count > 0) && (
                      <circle cx={projCenter.x} cy={projCenter.y} r={3} fill="#f87171" />
                    )}
                  </g>
                );
              })
            ) : (
              <text
                x={labelPos.x}
                y={labelPos.y}
                textAnchor="middle"
                className="fill-slate-600"
                style={{ fontSize: 10 }}
              >
                No zones configured
              </text>
            )}

            <rect
              x={labelPos.x - 60}
              y={labelPos.y + 30}
              width={120}
              height={36}
              rx={4}
              fill="rgb(15 23 42 / 0.92)"
              stroke={isSelected ? "#38bdf8" : "rgb(51 65 85)"}
              strokeWidth={isSelected ? 1.5 : 1}
            />
            <text x={labelPos.x} y={labelPos.y + 44} textAnchor="middle" className="fill-slate-200" style={{ fontSize: 11, fontWeight: 600 }}>
              {cfg.camera.camera_id}
            </text>
            <text x={labelPos.x} y={labelPos.y + 58} textAnchor="middle" className="fill-slate-400" style={{ fontSize: 9.5 }}>
              {summary ? `${summary.people_count} people${summary.hazard_count > 0 ? ` · ${summary.hazard_count} hazard` : ""}` : "Not reporting"}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
