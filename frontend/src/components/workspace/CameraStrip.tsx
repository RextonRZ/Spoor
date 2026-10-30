"use client";
/**
 * Camera route strip (QUEUE H3 / H10, owner_ideas_0303 §3): the cameras along the parcel's route, in time order, one
 * tile each, so the gap is obvious at a glance. Tiles: a frame at a scan's time from the camera that watches that read
 * point ("not analysed" until tracking runs), the cameras where it was expected next (dashed: grey not analysed, red
 * not seen), and a grey "no camera" tile after the trail ends. Arrows between tiles carry the time and how it moved
 * ("+4.7 s · belt, inferred"). Click a tile to open that frame in the hero.
 */
import { FadeImg } from "@/components/ui";
import { useEffect, useState } from "react";
import { api, signedUrl } from "@/lib/api";
import { camId, scanPoint } from "@/lib/hub";
import { describeScan } from "@/lib/scans";
import { cam, clock, RESULT_WORDS, type ExpectedNext, type JourneyScan } from "@/lib/journey";
import { toMs } from "@/lib/time";
import { useWorkspace } from "./context";

interface Tile {
  key: string;
  camera: string | null; // backend id
  t: string;
  title: string;
  sub: string;
  kind: "scan" | "seen" | "expected" | "not_seen" | "none";
  link?: string; // arrow text before this tile
  region?: [number, number, number, number] | null;
  basis?: [number, number] | null;
}

export default function CameraStrip() {
  const { journey, missing, cameras, select } = useWorkspace();
  const j = journey.data?.objects[0];
  const mm = missing.data?.objects[0];
  if (!j || !cameras.data) return null;
  const covered = (backendId: string, t: string) => cameras.data!.find((r) => r.camera.camera_id === backendId)
    ?.coverage.some((c) => toMs(c.start_utc) <= toMs(t) && toMs(t) <= toMs(c.end_utc));
  const tiles: Tile[] = [];
  let prevT: string | null = null;
  const linkTo = (t: string) => {
    if (!prevT) return undefined;
    const seg = j.segments.find((s) => s.kind === "inferred_along_conveyor" && Math.abs(toMs(s.end) - toMs(t)) < 50);
    const dt = ((toMs(t) - toMs(prevT)) / 1000).toFixed(1);
    return seg ? `+${dt} s · belt` : `+${dt} s`;
  };
  j.scans.forEach((s: JourneyScan) => {
    const viewer = scanPoint(s.station_id ?? s.device_id)?.visible_by.map(camId.toBackend).find((c) => covered(c, s.t));
    tiles.push({ key: s.scan_event_id, camera: viewer ?? null, t: s.t, title: viewer ? cam(viewer) : "no camera with footage",
      sub: `${describeScan(s).title.replace(/ \(line [AB]\)/, "")} · ${clock(s.t, true)}`, kind: viewer ? "scan" : "none", link: linkTo(s.t) });
    prevT = s.t;
  });
  const last = j.last_confirmed;
  const later = (mm?.expected_next ?? []).filter((r: ExpectedNext) => r.role !== "watching_last_point" && r.result !== "no_footage");
  later.forEach((r) => tiles.push({ key: `x${r.camera_id}`, camera: r.camera_id, t: r.predicted_t, title: cam(r.camera_id),
    sub: `expected ${clock(r.window.start, true).replace(" MYT", "")}–${clock(r.window.end, true)} · ${RESULT_WORDS[r.result]}`,
    kind: r.result === "not_seen" ? "not_seen" : r.result === "seen" ? "seen" : "expected", region: r.expected_region_px,
    basis: r.region_basis_wh_px, link: last ? `${r.how}` : undefined }));
  if (last) tiles.push({ key: "after", camera: null, t: last.t, title: "no camera", sub: `after ${clock(last.t, true)}: unknown`, kind: "none",
    link: later.length ? undefined : "then" });
  return (
    <section className="cs" aria-label="Cameras along the route, in time order" data-testid="camera-strip">
      <ol className="cs-row">
        {tiles.map((t) => (
          <li key={t.key} className="cs-item">
            {t.link && <span className="cs-link" aria-hidden>{t.link}</span>}
            <TileView t={t} onOpen={() => t.camera && select({ kind: "camera", cameraId: t.camera, time: toMs(t.t) })} />
          </li>
        ))}
      </ol>
    </section>
  );
}

function TileView({ t, onOpen }: { t: Tile; onOpen: () => void }) {
  const { cameras } = useWorkspace();
  const [url, setUrl] = useState<string | null>(null);
  const media = t.camera ? cameras.data?.find((r) => r.camera.camera_id === t.camera)?.coverage
    .find((c) => toMs(c.start_utc) <= toMs(t.t) && toMs(t.t) <= toMs(c.end_utc))?.media_id : undefined;
  useEffect(() => {
    if (!media) return;
    let live = true;
    api<{ frame_url: string }>(`/v1/media/${media}/frame-at?time=${encodeURIComponent(t.t)}`)
      .then((r) => live && setUrl(r.frame_url)).catch(() => {});
    return () => { live = false; };
  }, [media, t.t]);
  const r = t.region;
  const b = t.basis;
  return (
    <button className="cs-tile" data-kind={t.kind} onClick={onOpen} disabled={!t.camera}
      aria-label={`${t.title}: ${t.sub}${t.camera ? ". Open this frame." : ""}`}>
      <span className="cs-shot">
        {url ? <FadeImg src={signedUrl(url)} alt="" /> : <span className="cs-none">{t.kind === "none" ? "no camera" : ""}</span>}
        {r && b && url && <span className="cs-box" style={{ left: `${(r[0] / b[0]) * 100}%`, top: `${(r[1] / b[1]) * 100}%`,
          width: `${((r[2] - r[0]) / b[0]) * 100}%`, height: `${((r[3] - r[1]) / b[1]) * 100}%` }} />}
      </span>
      <span className="cs-title sp-num">{t.title}</span>
      <span className="cs-sub">{t.sub}</span>
    </button>
  );
}
