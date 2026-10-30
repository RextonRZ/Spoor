"use client";
/**
 * Plan-built 3D (QUEUE H6): the hub extruded from the site plan alone (GET /sites/{id}/plan), no 3D model. This is
 * what a real hub gets on day one from its floor plan: walls (cut away at 3 m so the inside stays visible), zones,
 * conveyors as decks at their real heights, racks and benches as blocks, camera poses, and the same evidence styles as
 * the 2D journey (amber dotted inferred, blue scan beads, the trail end and the computed "could be here" area).
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, Line, OrbitControls } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useResource } from "@/lib/api";
import { siteToRenderer, type Vec3 } from "@/lib/frames";
import { cam, cloudAt, inPlayCameras, type XY } from "@/lib/journey";
import { ZONE_NAMES } from "@/components/plan/HubPlan";
import { useWorkspace } from "./context";

interface Plan {
  outline_m: XY[];
  eaves_m: number | null;
  areas: { area_id: string; kind: string; name: string; polygon_m: XY[]; height_m: number | null }[];
  conveyors: { conveyor_id: string; kind: string; path_m: XY[]; deck_heights_m: number[]; closed?: boolean }[];
  cameras: { camera_id: string; position_m: Vec3; heading_deg: number; tilt_down_deg: number; hfov_deg: number }[];
}

const v = (x: number, y: number, z = 0) => new THREE.Vector3(...siteToRenderer([x, y, z]));
const WALL_H = 3;
const ACCENT = "#6366F1"; // brand indigo: cameras in play only, as in 2D

function flat(poly: XY[], y: number) {
  // a polygon on the floor plane at height y (renderer Y-up): shape in (x, -siteY) so it maps under rotateX(-90deg)
  const shape = new THREE.Shape(poly.map(([x, sy]) => new THREE.Vector2(x, sy)));
  const g = new THREE.ShapeGeometry(shape);
  g.rotateX(-Math.PI / 2);
  g.translate(0, y, 0);
  return g;
}

function Box({ a, b, h0, h1, w, color }: { a: XY; b: XY; h0: number; h1: number; w: number; color: string }) {
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const mid = v((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (h0 + h1) / 2);
  const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
  return (
    <mesh position={mid} rotation={[0, ang, 0]}>
      <boxGeometry args={[len, Math.max(0.05, h1 - h0), w]} />
      <meshStandardMaterial color={color} roughness={0.9} />
    </mesh>
  );
}

/** Zone labels in screen space (review F-032 #2): bigger zones first; a label that would overlap one already shown or
 * leave the view is hidden until the orbit frees its spot. Checked every few frames, not every frame. */
function ZoneLabels({ zones }: { zones: { key: string; at: THREE.Vector3; text: string }[] }) {
  const els = useRef<(HTMLDivElement | null)[]>([]);
  const gl = useThree((st) => st.gl);
  const tick = useRef(0);
  useFrame(() => {
    if (tick.current++ % 6) return;
    const view = gl.domElement.getBoundingClientRect();
    const kept: DOMRect[] = [];
    els.current.forEach((el) => {
      if (!el) return;
      const r = el.getBoundingClientRect();
      const inside = r.left >= view.left + 2 && r.right <= view.right - 2 && r.top >= view.top + 2 && r.bottom <= view.bottom - 2;
      const clear = !kept.some((k) => r.left < k.right + 4 && k.left < r.right + 4 && r.top < k.bottom + 2 && k.top < r.bottom + 2);
      const show = r.width > 0 && inside && clear;
      el.style.visibility = show ? "visible" : "hidden";
      if (show) kept.push(r);
    });
  });
  return <>{zones.map((z, i) => (
    <Html key={z.key} position={z.at} center>
      <div ref={(el) => { els.current[i] = el; }} className="p3-label" style={{ visibility: "hidden" }}>{z.text}</div>
    </Html>
  ))}</>;
}

function Scene({ plan }: { plan: Plan }) {
  const { journey, possible, playhead, missing, litCameras } = useWorkspace();
  const inPlay = new Set(inPlayCameras(litCameras, missing.data?.objects[0]));
  const j = journey.data?.objects[0];
  const step = cloudAt(possible.data?.objects[0], playhead);
  const floor = useMemo(() => flat(plan.outline_m, 0), [plan]);
  const zones = useMemo(() => plan.areas.filter((a) => a.kind === "zone" || a.kind === "store").map((a) => ({ a, g: flat(a.polygon_m, 0.01) })), [plan]);
  const cloud = useMemo(() => (step ? step.polygons.map((p) => flat(p, 0.03)) : []), [step]);
  const labels = useMemo(() => zones.map(({ a }) => {
    const code = a.name.match(/^Z\d+/)?.[0] ?? "";
    const xs = a.polygon_m.map((p) => p[0]);
    const ys = a.polygon_m.map((p) => p[1]);
    const at = v(xs.reduce((s, x) => s + x, 0) / xs.length, ys.reduce((s, y) => s + y, 0) / ys.length, 0.05);
    const area = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
    return { key: a.area_id, at, area, text: ZONE_NAMES[code] ?? a.name.replace(/^Z\d+ /, "").replace(/ \(.*\)$/, "") };
  }).sort((p, q) => q.area - p.area), [zones]);
  const deck = (c: Plan["conveyors"][number], i: number) => c.deck_heights_m[Math.min(i, c.deck_heights_m.length - 1)];
  return (
    <>
      <ambientLight intensity={1.1} />
      <directionalLight position={[20, 40, 10]} intensity={1.2} />
      <mesh geometry={floor}><meshStandardMaterial color="#20222a" /></mesh>
      {zones.map(({ a, g }) => (
        <mesh key={a.area_id} geometry={g}><meshBasicMaterial color={a.kind === "store" ? "#343744" : "#272a33"} /></mesh>
      ))}
      <ZoneLabels zones={labels} />
      {plan.outline_m.map((p, i) => {
        const q = plan.outline_m[(i + 1) % plan.outline_m.length];
        return <Box key={`w${i}`} a={p} b={q} h0={0} h1={WALL_H} w={0.3} color="#6b707c" />;
      })}
      {plan.areas.filter((a) => a.kind === "rack" || a.kind === "bench").map((a) => {
        const xs = a.polygon_m.map((p) => p[0]);
        const ys = a.polygon_m.map((p) => p[1]);
        const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
        const h = a.height_m ?? 1;
        return (
          <mesh key={a.area_id} position={v((x0 + x1) / 2, (y0 + y1) / 2, h / 2)}>
            <boxGeometry args={[x1 - x0, h, y1 - y0]} />
            <meshStandardMaterial color={a.kind === "rack" ? "#55596a" : "#454957"} />
          </mesh>
        );
      })}
      {plan.conveyors.flatMap((c) => {
        const pts = c.closed ? [...c.path_m, c.path_m[0]] : c.path_m;
        return pts.slice(1).map((b, i) => (
          <Box key={`${c.conveyor_id}${i}`} a={pts[i]} b={b} h0={deck(c, i) - 0.12} h1={deck(c, i)} w={c.kind === "chute" ? 0.9 : 0.8}
            color={c.kind === "loop" ? "#5a5f6e" : "#4a4e5c"} />
        ));
      })}
      {plan.cameras.map((c) => {
        const h = (c.heading_deg * Math.PI) / 180;
        const tip = v(c.position_m[0] + Math.cos(h) * 1.6, c.position_m[1] + Math.sin(h) * 1.6, c.position_m[2] - 1.2);
        if (inPlay.has(cam(c.camera_id))) return <InPlayCamera key={c.camera_id} c={c} />;
        return (
          <group key={c.camera_id}>
            <mesh position={v(...c.position_m)}><sphereGeometry args={[0.25, 12, 12]} /><meshBasicMaterial color="#8b909b" /></mesh>
            <Line points={[v(...c.position_m), tip]} color="#5a5f69" lineWidth={1.5} />
          </group>
        );
      })}
      {cloud.map((g, i) => (
        <mesh key={`cl${i}`} geometry={g}><meshBasicMaterial color="#c9ccd3" transparent opacity={0.18} depthWrite={false} /></mesh>
      ))}
      {j?.segments.filter((s) => s.kind === "inferred_along_conveyor").map((s, i) => (
        <Line key={`inf${i}`} points={s.path_m.map((p) => v(p[0], p[1], 1.65))} color="#fbbf24" lineWidth={3} dashed dashSize={0.25} gapSize={0.35} />
      ))}
      {j?.scans.filter((s) => s.xy).map((s) => (
        <mesh key={s.scan_event_id} position={v(s.xy![0], s.xy![1], 1.75)} rotation={[0, Math.PI / 4, 0]}>
          <octahedronGeometry args={[0.35]} /><meshBasicMaterial color="#60a5fa" />
        </mesh>
      ))}
      {j?.last_confirmed?.xy && (
        <mesh position={v(j.last_confirmed.xy[0], j.last_confirmed.xy[1], 0.05)} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.1, 1.35, 40]} /><meshBasicMaterial color="#8b909b" />
        </mesh>
      )}
      <OrbitControls makeDefault target={v(30, 18, 0)} maxPolarAngle={Math.PI / 2.1} />
    </>
  );
}

/** A camera in play: indigo, with its view wedge on the floor (8 m, as in 2D) and edge rays from the lens. */
function InPlayCamera({ c }: { c: Plan["cameras"][number] }) {
  const [x, y, z] = c.position_m;
  const h = (c.heading_deg * Math.PI) / 180;
  const half = (c.hfov_deg * Math.PI) / 360;
  const fan = useMemo(() => {
    const rng = 8;
    const edge = (a: number) => [x + rng * Math.cos(a), y + rng * Math.sin(a)] as XY;
    const pts: XY[] = [[x, y], ...Array.from({ length: 13 }, (_, i) => edge(h - half + (2 * half * i) / 12))];
    return { g: flat(pts, 0.04), l: v(...edge(h - half), 0.04), r: v(...edge(h + half), 0.04) };
  }, [x, y, h, half]);
  const lens = v(x, y, z);
  return (
    <group>
      <mesh geometry={fan.g}><meshBasicMaterial color={ACCENT} transparent opacity={0.12} depthWrite={false} /></mesh>
      <Line points={[lens, fan.l]} color={ACCENT} lineWidth={1.2} transparent opacity={0.6} />
      <Line points={[lens, fan.r]} color={ACCENT} lineWidth={1.2} transparent opacity={0.6} />
      <mesh position={lens}><sphereGeometry args={[0.38, 16, 16]} /><meshBasicMaterial color={ACCENT} /></mesh>
      <Html position={v(x, y, z + 0.9)} center><div className="p3-label p3-cam">{cam(c.camera_id).replace("_", " ")}</div></Html>
    </group>
  );
}

export default function PlanScene3D() {
  const { siteId } = useWorkspace();
  const plan = useResource<Plan>(siteId ? `/v1/sites/${siteId}/plan` : null);
  if (!plan.data) return <div className="sp-scene-note" role="status">{plan.error ? "No site plan imported." : "Loading the site plan"}</div>;
  return (
    <div className="sp-scene" data-ready="true" aria-label="3D view extruded from the site plan">
      <Canvas camera={{ position: v(30, -26, 52).toArray(), fov: 42 }} dpr={[1, 2]}>
        <color attach="background" args={["#0b0c10"]} />
        <Scene plan={plan.data} />
      </Canvas>
    </div>
  );
}
