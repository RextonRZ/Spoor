"use client";
/**
 * Cameras, as a live monitor (owner 31 Oct: "real time, open the camera, zoom in", not a scrubber): a wall of every
 * camera with its name, a REC dot and a running clock; pick one and it opens big in the docked viewer (zoom, pan, full
 * screen). Cameras with a moving feed play it in a loop while visible; the rest show their still. Zone tabs filter the
 * wall; the 3D hub is one switch away. Same split-view frame as the Hub: the wall on the left, the chosen camera docked
 * on the right (narrower screens: it slides in).
 */
import Link from "next/link";
import { useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useResource } from "@/lib/api";
import { HUB, camId } from "@/lib/hub";
import type { Site } from "@/lib/types";
import { CameraSetup } from "@/components/case/CameraSetup";
import { Drawer, Tabs, WIDE, onWideChange } from "@/components/hub/parts";
import { Clock, Feed, useFeeds } from "@/components/cameras/Feed";
import { Viewer } from "@/components/cameras/Viewer";
import "./cameras.css";


// zones as the prototype groups them (by where each camera looks)
const ZONE_OF: Record<string, "in" | "sort" | "out"> = {
  CAM_01: "in", CAM_02: "in", CAM_03: "in", CAM_18: "in", CAM_04: "sort", CAM_05: "sort", CAM_06: "sort", CAM_07: "sort", CAM_08: "sort",
  CAM_09: "sort", CAM_10: "sort", CAM_11: "sort", CAM_12: "sort", CAM_13: "out", CAM_14: "out", CAM_15: "out", CAM_16: "out", CAM_17: "out", CAM_19: "out",
};
type Zone = "all" | "in" | "sort" | "out";
const ZONES: [Zone, string][] = [["all", "All"], ["in", "Inbound"], ["sort", "Sorting"], ["out", "Outbound"]];

interface Inbox { as_of: string | null }
interface Dashboard { cases: { case_id: string; status: string }[] }
interface Missing { objects: { expected_next: { camera_id: string }[] }[] }

const camWords = (osd: string) => osd.toLowerCase().replace(/^\w/, (c) => c.toUpperCase()).replace(/(c\d{2})-(c\d{2})/i, (_, a: string, b: string) => `${a.toUpperCase()} to ${b.toUpperCase()}`)
  .replace(/(\d{2})-(\d{2})/, "$1 to $2");
const mountWords = (m: string) => m.replace(/\s*\(.*\)$/, "").replace(/^\w/, (c) => c.toUpperCase());

export default function CamerasPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const inbox = useResource<Inbox>(site ? `/v1/sites/${site.site_id}/exceptions?limit=1` : null);
  const dash = useResource<Dashboard>(site ? `/v1/sites/${site.site_id}/dashboard` : null);
  const openCase = dash.data?.cases.find((c) => c.status !== "found")?.case_id;
  const mm = useResource<Missing>(openCase ? `/v1/cases/${openCase}/missing-moment` : null);
  const feeds = useFeeds();
  const wide = useSyncExternalStore(onWideChange, () => window.matchMedia(WIDE).matches, () => true);
  const [zone, setZone] = useState<Zone>("all");
  const [view, setView] = useState<"wall" | "3d">("wall");
  const [sel, setSel] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);

  // the recorder's clock starts at the scan log's latest time (else mid-shift) and runs from there
  const baseMs = useMemo(() => (inbox.data?.as_of ? Date.parse(inbox.data.as_of) : Date.parse("2026-10-28T14:34:00+08:00")), [inbox.data]);
  const inCase = useMemo(() => new Set((mm.data?.objects[0]?.expected_next ?? []).map((r) => camId.toHub(r.camera_id))), [mm.data]);
  const counts = (z: Zone) => HUB.cameras.filter((c) => z === "all" || ZONE_OF[c.id] === z).length;
  const cams = HUB.cameras.filter((c) => zone === "all" || ZONE_OF[c.id] === zone);
  const tabs = ZONES.map(([id, label]) => ({ id, label, n: counts(id) }));
  // docked: the first camera that could see the case's parcel next (else the first camera) is open from the start
  const first = cams.find((c) => inCase.has(c.id)) ?? cams[0];
  const chosen = HUB.cameras.find((c) => c.id === sel) ?? (wide ? first : undefined);
  const pick = (id: string, el: HTMLElement) => { opener.current = el; setSel(id); };
  const close = () => { setSel(null); opener.current?.focus(); };
  const live = Object.keys(feeds).length;

  const detail = (c: NonNullable<typeof chosen>) => (
    <>
      <Viewer key={c.id} id={c.id} label={camWords(c.osd_label)} src={feeds[c.id]} baseMs={baseMs} />
      <h2 className="hb-d-h">{camWords(c.osd_label)}</h2>
      <dl className="cm-facts">
        <div><dt>Zone</dt><dd>{{ in: "Inbound", sort: "Sorting", out: "Outbound" }[ZONE_OF[c.id]]}</dd></div>
        <div><dt>Mounted</dt><dd>{c.height_m} m up · {mountWords(c.mount)}</dd></div>
        <div><dt>Picture</dt><dd>{c.resolution[0]} × {c.resolution[1]}</dd></div>
      </dl>
      {inCase.has(c.id) && openCase && (
        <Link className="hb-btn hb-btn-primary" href={`/cases/${openCase}/proof`}>Watch it in the case</Link>
      )}
    </>
  );

  return (
    <div className="hb cm">
      <header className="hb-head">
        <div>
          <h1 className="hb-title" data-testid="cameras-title">Cameras</h1>
          <p className="hb-sub"><i className="cm-livedot" aria-hidden="true" />{HUB.cameras.length} cameras · live view{live ? ` · ${live} moving feeds` : ""}</p>
        </div>
        <div className="cm-seg" role="group" aria-label="View">
          <button type="button" aria-pressed={view === "wall"} onClick={() => setView("wall")}>Camera wall</button>
          <button type="button" aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D hub</button>
        </div>
      </header>

      {view === "3d" ? (
        // Rexton 3 Nov: the 3D hub is the Blender model with every camera on it (click one to look through it)
        <div className="ht cm-setup"><CameraSetup /></div>
      ) : (
        <div className={wide ? "hb-split cm-split" : "hb-stack"}>
          <div className="hb-left">
            <section className="hb-panel cm-panel" aria-label="Camera wall">
              <div className="hb-tabbar"><Tabs tabs={tabs} tab={zone} onTab={setZone} /></div>
              <div className="cm-grid">
                {cams.map((c) => (
                  <button key={c.id} type="button" className="cm-tile" aria-pressed={chosen?.id === c.id} onClick={(e) => pick(c.id, e.currentTarget)}
                    aria-label={`${c.id.replace("_", " ")}, ${camWords(c.osd_label)}. Open the live view.`}>
                    <Feed id={c.id} src={feeds[c.id]} />
                    <span className="cf-osd" aria-hidden="true">
                      <span className="cf-name">{c.id.replace("_", " ")}<em>{camWords(c.osd_label)}</em></span>
                      <span className="cf-meta"><i className="cf-rec" /><Clock baseMs={baseMs} /></span>
                    </span>
                    {inCase.has(c.id) && <span className="cm-incase">In a case</span>}
                  </button>
                ))}
              </div>
            </section>
          </div>
          {wide && chosen && (
            <aside className="hb-dock cm-dock" aria-label="Camera view">
              <div className="hb-dock-in" key={chosen.id}>
                <div className="hb-drawer-head"><span className="hb-chip" data-tone="ok">Live</span><span className="hb-drawer-place">{chosen.id.replace("_", " ")}</span></div>
                <div className="hb-drawer-body">{detail(chosen)}</div>
              </div>
            </aside>
          )}
        </div>
      )}

      {view === "wall" && !wide && chosen && (
        <Drawer key={chosen.id} label={`${chosen.id.replace("_", " ")} live view`} onClose={close}
          head={(x) => <div className="hb-drawer-head"><span className="hb-chip" data-tone="ok">Live</span><span className="hb-drawer-place">{chosen.id.replace("_", " ")}</span>{x}</div>}>
          {detail(chosen)}
        </Drawer>
      )}
    </div>
  );
}
