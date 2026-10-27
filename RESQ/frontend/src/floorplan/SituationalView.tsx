import { useCallback, useMemo, useRef, useState } from "react";
import type { IncidentState } from "../types/incident";
import type { ExitConfig, ZoneConfig } from "../types/building";
import { exitFillColor, exitStrokeColor, exitStateStyles, zoneFillColor, zoneStrokeColor } from "../lib/theme";
import { personLabel } from "../lib/humanize";
import {
  type Camera,
  type Vec3,
  centroid,
  clampPitch,
  imageToGround,
  project,
  spreadOffset,
  toPointsAttr,
} from "./scene3d";

interface Props {
  incident: IncidentState | null;
  zones: ZoneConfig[];
  exits: ExitConfig[];
  imageWidth: number;
  imageHeight: number;
  configError?: string | null;
  /** True only while the config fetch is genuinely in flight — lets this
      view distinguish "still loading" from "loaded, and there's honestly
      nothing configured yet" (e.g. a camera with no calibrated zones). */
  configLoading?: boolean;
}

const VIEW_W = 640;
const VIEW_H = 420;
const PLANE_SCALE = 520;
const DEFAULT_CAMERA: Camera = { yaw: -0.42, pitch: 0.92, zoom: 1 };

/** Height (world units) of the extruded zone slabs and marker posts. */
const ZONE_HEIGHT = 10;
const PERSON_HEIGHT = 46;
const EXIT_HEIGHT = 54;

type Drawable = { depth: number; el: JSX.Element };

export default function SituationalView({
  incident,
  zones,
  exits,
  imageWidth,
  imageHeight,
  configError,
  configLoading = false,
}: Props) {
  const [camera, setCamera] = useState<Camera>(DEFAULT_CAMERA);
  const dragRef = useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Zone/exit polygons rarely fill the whole camera frame, so centre the view
  // on the geometry that actually exists rather than on the image centre —
  // otherwise the scene renders small and off to one side.
  const geometryCenter = useMemo(() => {
    const pts = [...zones.flatMap((z) => z.polygon), ...exits.flatMap((e) => e.polygon)];
    if (pts.length === 0) return { cx: imageWidth / 2, cy: imageHeight / 2, spread: 1 };
    const xs = pts.map(([x]) => x);
    const ys = pts.map(([, y]) => y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    return {
      cx: (minX + maxX) / 2,
      cy: (minY + maxY) / 2,
      spread: Math.max(maxX - minX, maxY - minY) / Math.max(imageWidth, imageHeight),
    };
  }, [zones, exits, imageWidth, imageHeight]);

  // Scale so the geometry comfortably fills the viewport, and recentre by
  // shifting the sampled image point to the geometry's centre.
  const planeScale = PLANE_SCALE / Math.max(0.28, Math.min(1, geometryCenter.spread));
  const toGround = useCallback(
    (px: number, py: number): Vec3 =>
      imageToGround(
        px - geometryCenter.cx + imageWidth / 2,
        py - geometryCenter.cy + imageHeight / 2,
        imageWidth,
        imageHeight,
        planeScale,
      ),
    [geometryCenter, imageWidth, imageHeight, planeScale],
  );
  const polyToGround = useCallback(
    (polygon: [number, number][]): Vec3[] => polygon.map(([px, py]) => toGround(px, py)),
    [toGround],
  );

  const p = useCallback(
    (v: Vec3) => project(v, camera, VIEW_W, VIEW_H),
    [camera],
  );

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, yaw: camera.yaw, pitch: camera.pitch };
    setIsDragging(true);
  };

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const d = dragRef.current;
    if (!d) return;
    setCamera((c) => ({
      ...c,
      yaw: d.yaw + (e.clientX - d.x) * 0.006,
      pitch: clampPitch(d.pitch + (e.clientY - d.y) * 0.004),
    }));
  };

  const endDrag = () => {
    dragRef.current = null;
    setIsDragging(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<SVGSVGElement>) => {
    const step = 0.12;
    if (e.key === "ArrowLeft") setCamera((c) => ({ ...c, yaw: c.yaw - step }));
    else if (e.key === "ArrowRight") setCamera((c) => ({ ...c, yaw: c.yaw + step }));
    else if (e.key === "ArrowUp") setCamera((c) => ({ ...c, pitch: clampPitch(c.pitch - step / 2) }));
    else if (e.key === "ArrowDown") setCamera((c) => ({ ...c, pitch: clampPitch(c.pitch + step / 2) }));
    else if (e.key === "+" || e.key === "=") setCamera((c) => ({ ...c, zoom: Math.min(2.2, c.zoom * 1.12) }));
    else if (e.key === "-") setCamera((c) => ({ ...c, zoom: Math.max(0.5, c.zoom / 1.12) }));
    else return;
    e.preventDefault();
  };

  const hazardPresent = (incident?.hazards.length ?? 0) > 0;

  // Ground-space geometry (the actual trig/projection-independent math) is
  // memoized separately from the per-tick drawable list below: it only
  // depends on zones/exits/image dimensions, so it's untouched by both a
  // 2s incident poll and by every mousemove during a drag — previously
  // this was recomputed from scratch on every single one of those, which
  // is the "diff/patch instead of full rebuild" performance ask.
  const zoneGeometry = useMemo(
    () =>
      zones.map((zone) => {
        const ground = polyToGround(zone.polygon);
        const top = ground.map((v) => ({ ...v, y: ZONE_HEIGHT }));
        return { zone, ground, top, groundCentroid: centroid(top) };
      }),
    [zones, polyToGround],
  );

  const exitGeometry = useMemo(
    () =>
      exits.map((exitConfig) => {
        const ground = polyToGround(exitConfig.polygon);
        return { exitConfig, ground, groundCentroid: centroid(ground) };
      }),
    [exits, polyToGround],
  );

  const zoneCentroidsById = useMemo(() => {
    const m = new Map<string, Vec3>();
    for (const zg of zoneGeometry) m.set(zg.zone.id, zg.groundCentroid);
    return m;
  }, [zoneGeometry]);

  const drawables = useMemo<Drawable[]>(() => {
    const items: Drawable[] = [];

    // ---- Zones: extruded slabs on the ground plane.
    for (const { zone, ground, top, groundCentroid: c } of zoneGeometry) {
      const projTop = top.map(p);
      const projC = p(c);
      const occupancy = incident?.congestion[zone.id]?.occupancy ?? 0;
      const isDanger = zone.type === "danger";
      const emphasise = isDanger && hazardPresent;

      // Side walls give the slab visible thickness.
      for (let i = 0; i < ground.length; i++) {
        const a = ground[i];
        const b = ground[(i + 1) % ground.length];
        const quad = [a, b, { ...b, y: ZONE_HEIGHT }, { ...a, y: ZONE_HEIGHT }].map(p);
        const depth = (quad[0].depth + quad[1].depth) / 2;
        items.push({
          depth,
          el: (
            <polygon
              key={`${zone.id}-wall-${i}`}
              points={toPointsAttr(quad)}
              fill={zoneStrokeColor[zone.type]}
              fillOpacity={0.16}
            />
          ),
        });
      }

      items.push({
        depth: projC.depth,
        el: (
          <g key={`${zone.id}-top`}>
            <polygon
              points={toPointsAttr(projTop)}
              fill={zoneFillColor[zone.type]}
              stroke={zoneStrokeColor[zone.type]}
              strokeWidth={emphasise ? 2 : 1.25}
              strokeDasharray={zone.type === "obstruction" ? "6 4" : undefined}
            />
            <text
              x={projC.x}
              y={projC.y - 4}
              textAnchor="middle"
              className="fill-slate-200"
              style={{ fontSize: 11, fontWeight: 500 }}
            >
              {zone.label}
            </text>
            {occupancy > 0 && (
              <text
                x={projC.x}
                y={projC.y + 10}
                textAnchor="middle"
                className="fill-slate-400"
                style={{ fontSize: 10 }}
              >
                {occupancy} {occupancy === 1 ? "person" : "people"}
              </text>
            )}
          </g>
        ),
      });
    }

    // ---- Exits: vertical panels, coloured by their real state.
    for (const { exitConfig, ground, groundCentroid: c } of exitGeometry) {
      const state = incident?.exits.find((e) => e.exit_id === exitConfig.id)?.state ?? "CLEAR";
      const base = p(c);
      const topPt = p({ ...c, y: EXIT_HEIGHT });
      const pad = ground.map(p);

      items.push({
        depth: base.depth,
        el: (
          <g key={`${exitConfig.id}-pad`}>
            <polygon
              points={toPointsAttr(pad)}
              fill={exitFillColor[state]}
              stroke={exitStrokeColor[state]}
              strokeWidth={1.5}
            />
          </g>
        ),
      });

      items.push({
        depth: base.depth - 0.01,
        el: (
          <g key={`${exitConfig.id}-post`}>
            <line
              x1={base.x}
              y1={base.y}
              x2={topPt.x}
              y2={topPt.y}
              stroke={exitStrokeColor[state]}
              strokeWidth={2}
            />
            <rect
              x={topPt.x - 30}
              y={topPt.y - 20}
              width={60}
              height={17}
              rx={3}
              fill="rgb(15 23 42 / 0.92)"
              stroke={exitStrokeColor[state]}
              strokeWidth={1}
            />
            <text
              x={topPt.x}
              y={topPt.y - 8}
              textAnchor="middle"
              style={{ fontSize: 10, fontWeight: 600 }}
              fill={exitStrokeColor[state]}
            >
              {exitConfig.id} {exitStateStyles[state].icon}
            </text>
          </g>
        ),
      });
    }

    // ---- People: positioned at zone level (RESQ tracks zone membership,
    // not metric ground position — see the note under the view).
    const unzonedAnchor = toGround(imageWidth * 0.5, imageHeight * 0.04);

    for (const person of incident?.people ?? []) {
      const anchor = person.current_zone ? zoneCentroidsById.get(person.current_zone) ?? unzonedAnchor : unzonedAnchor;
      const { dx, dz } = spreadOffset(person.track_id, 42);
      const foot: Vec3 = { x: anchor.x + dx, y: 0, z: anchor.z + dz };
      const head: Vec3 = { ...foot, y: PERSON_HEIGHT };
      const pf = p(foot);
      const ph = p(head);
      const inDanger = Boolean(
        person.current_zone && zones.find((z) => z.id === person.current_zone)?.type === "danger",
      );
      const color = inDanger ? "#f87171" : "#7dd3fc";

      items.push({
        depth: pf.depth,
        el: (
          <g key={`person-${person.track_id}`}>
            <ellipse cx={pf.x} cy={pf.y} rx={7} ry={3} fill="rgb(2 6 23 / 0.55)" />
            <line x1={pf.x} y1={pf.y} x2={ph.x} y2={ph.y} stroke={color} strokeWidth={3} strokeLinecap="round" />
            <circle cx={ph.x} cy={ph.y} r={5} fill={color} stroke="rgb(15 23 42)" strokeWidth={1.25} />
            <text
              x={ph.x}
              y={ph.y - 11}
              textAnchor="middle"
              className="fill-slate-200"
              style={{ fontSize: 10, fontWeight: 600 }}
            >
              {personLabel(person.track_id)}
            </text>
          </g>
        ),
      });
    }

    return items.sort((a, b) => b.depth - a.depth);
  }, [zoneGeometry, exitGeometry, zoneCentroidsById, incident, imageWidth, imageHeight, p, hazardPresent, toGround, zones]);

  const hasGeometry = zones.length > 0 || exits.length > 0;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-200">Situational view</h2>
          <p className="text-xs text-slate-500">Configured zones, exits and tracked people</p>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setCamera((c) => ({ ...c, zoom: Math.max(0.5, c.zoom / 1.15) }))}
            className="h-7 w-7 rounded border border-slate-700 bg-slate-800/60 text-slate-300 hover:bg-slate-700/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            aria-label="Zoom out"
          >
            −
          </button>
          <button
            type="button"
            onClick={() => setCamera((c) => ({ ...c, zoom: Math.min(2.2, c.zoom * 1.15) }))}
            className="h-7 w-7 rounded border border-slate-700 bg-slate-800/60 text-slate-300 hover:bg-slate-700/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            aria-label="Zoom in"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => setCamera(DEFAULT_CAMERA)}
            className="h-7 rounded border border-slate-700 bg-slate-800/60 px-2 text-xs text-slate-300 hover:bg-slate-700/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            Reset
          </button>
        </div>
      </div>

      <div className="relative flex-1 overflow-hidden rounded-md border border-slate-800 bg-slate-950">
        {configError ? (
          <div className="flex h-full items-center justify-center p-6 text-center">
            <p className="text-sm text-slate-400">
              Building layout unavailable — {configError}
            </p>
          </div>
        ) : configLoading ? (
          <div className="flex h-full items-center justify-center p-6 text-center">
            <p className="text-sm text-slate-500">Loading building layout…</p>
          </div>
        ) : !hasGeometry ? (
          <div className="flex h-full items-center justify-center p-6 text-center">
            <p className="text-sm text-slate-500">
              No zones or exits configured for this camera yet.
            </p>
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className={`h-full w-full touch-none select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500 ${
              isDragging ? "cursor-grabbing" : "cursor-grab"
            }`}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerLeave={endDrag}
            onKeyDown={onKeyDown}
            tabIndex={0}
            role="img"
            aria-label={
              `3D situational view. ${zones.length} zones, ${exits.length} exits, ` +
              `${incident?.people.length ?? 0} people tracked. ` +
              `Drag or use arrow keys to rotate, plus and minus to zoom.`
            }
          >
            <GroundGrid camera={camera} planeScale={planeScale} />
            {drawables.map((d) => d.el)}
          </svg>
        )}
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-2xs text-slate-500">
        <LegendSwatch color="#ef4444" label="Danger area" />
        <LegendSwatch color="#f59e0b" label="Obstruction" />
        <LegendSwatch color="#94a3b8" label="Safe ground" />
        <LegendSwatch color="#7dd3fc" label="Person" />
        <LegendSwatch color="#f87171" label="Person in danger" />
        <span className="ml-auto">Drag to rotate · arrow keys · +/− zoom</span>
      </div>
      <p className="mt-1.5 text-2xs leading-relaxed text-slate-600">
        People are shown at <span className="text-slate-500">zone level</span>, not exact ground
        position — RESQ tracks which configured zone a person is in, and does not claim real-world
        distance from a single camera.
      </p>
    </div>
  );
}

function GroundGrid({ camera, planeScale }: { camera: Camera; planeScale: number }) {
  const lines: JSX.Element[] = [];
  const half = planeScale * 0.62;
  const step = half / 5;
  for (let i = -5; i <= 5; i++) {
    const t = i * step;
    const a = project({ x: t, y: 0, z: -half }, camera, VIEW_W, VIEW_H);
    const b = project({ x: t, y: 0, z: half }, camera, VIEW_W, VIEW_H);
    const c = project({ x: -half, y: 0, z: t }, camera, VIEW_W, VIEW_H);
    const d = project({ x: half, y: 0, z: t }, camera, VIEW_W, VIEW_H);
    lines.push(
      <line key={`gx-${i}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="rgb(51 65 85 / 0.5)" strokeWidth={0.75} />,
      <line key={`gz-${i}`} x1={c.x} y1={c.y} x2={d.x} y2={d.y} stroke="rgb(51 65 85 / 0.5)" strokeWidth={0.75} />,
    );
  }
  return <g>{lines}</g>;
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2 w-2 rounded-sm" style={{ backgroundColor: color }} aria-hidden />
      {label}
    </span>
  );
}
