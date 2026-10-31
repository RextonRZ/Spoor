"use client";
/**
 * Camera wall (review 007 #1): the demo's opening hook. A scenario's synthetic CCTV clips, synchronized, then the
 * customer complaint, then the case. Scenarios come from the builder's manifest + <S>/case_input.json (inputs only).
 * A tile plays only backend media whose SHA-256 equals the render file's: same bytes, same evidence chain. Missing
 * renders and clips not yet imported are shown as such; nothing stands in for them.
 */
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import CameraWall, { type WallTile } from "@/components/wall/CameraWall";
import { Empty, ErrorState, Loading } from "@/components/ui";
import { api, useResource } from "@/lib/api";
import { hubCamera } from "@/lib/hub";
import { tileState, type ScenarioIndex, type WallScenario } from "@/lib/scenarios";
import { toMs } from "@/lib/time";
import type { CaseListRow, MediaRow, Site } from "@/lib/types";

export default function WallPage() {
  return (
    <Suspense fallback={<div className="sp-page"><Loading label="Loading camera wall" /></div>}>
      <Wall />
    </Suspense>
  );
}

function useScenarioIndex(scenario: string | null) {
  const [state, setState] = useState<{ data?: ScenarioIndex; error?: Error; key?: string }>({});
  const key = scenario ?? "";
  useEffect(() => {
    let live = true;
    fetch(`/api/scenarios${scenario ? `?scenario=${encodeURIComponent(scenario)}` : ""}`, { cache: "no-store" })
      .then((r) => r.json() as Promise<ScenarioIndex>)
      .then((data) => live && setState({ data, key }))
      .catch((error: Error) => live && setState({ error, key }));
    return () => { live = false; };
  }, [scenario, key]);
  return state.key === key ? state : {};
}

/** Every original clip on every site the user can see, keyed by SHA-256. */
function useMediaBySha() {
  const sites = useResource<Site[]>("/v1/sites");
  const [rows, setRows] = useState<MediaRow[] | null>(null);
  const ids = sites.data?.map((s) => s.site_id).join(",") ?? null;
  useEffect(() => {
    if (ids === null) return;
    let live = true;
    Promise.all(ids.split(",").filter(Boolean).map((id) => api<MediaRow[]>(`/v1/sites/${id}/media`)))
      .then((all) => live && setRows(all.flat())).catch(() => live && setRows([]));
    return () => { live = false; };
  }, [ids]);
  return { rows, error: sites.error };
}

function Wall() {
  const params = useSearchParams();
  const router = useRouter();
  const caseParam = params.get("case");
  const scenarioParam = params.get("scenario");
  const index = useScenarioIndex(scenarioParam);
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const media = useMediaBySha();

  // Default source: the first S1-S5 scenario with renders, else the first scenario, else the newest case with footage.
  useEffect(() => {
    if (caseParam || scenarioParam || !index.data || !cases.data) return;
    const sc = index.data.scenarios;
    const pick = sc.find((s) => s.scenario !== "S0" && s.rendered > 0) ?? sc.find((s) => s.rendered > 0);
    if (pick) router.replace(`/wall?scenario=${pick.scenario}`);
    else if (cases.data.length) router.replace(`/wall?case=${cases.data[0].case.case_id}`);
  }, [caseParam, scenarioParam, index.data, cases.data, router]);

  const scenario = index.data?.scenarios.find((s) => s.scenario === scenarioParam) ?? null;
  const theCase = cases.data?.find((c) => c.case.case_id === caseParam) ?? null;
  const scenarioCase = scenario ? cases.data?.find((c) => c.case.question.startsWith(`${scenario.scenario} · `)) : undefined;

  return (
    <div className="sp-page sp-stack" style={{ gap: 18 }}>
      <header className="sp-row sp-wrap" style={{ justifyContent: "space-between", alignItems: "flex-end", gap: 12 }}>
        <div>
          <h1 className="sp-h1">Camera wall</h1>
        </div>
        <SourcePicker index={index.data} cases={cases.data ?? []} value={scenarioParam ? `s:${scenarioParam}` : caseParam ? `c:${caseParam}` : ""}
          onChange={(v) => router.replace(v.startsWith("s:") ? `/wall?scenario=${v.slice(2)}` : `/wall?case=${v.slice(2)}`)} />
      </header>
      {index.error && <ErrorState error={index.error} what="the scenario manifest" />}
      {media.error && <ErrorState error={media.error} what="footage" />}
      {scenarioParam && index.data && !scenario && (
        <Empty title={index.data.found ? `Scenario ${scenarioParam} is not in the manifest` : "Scenario manifest not written yet: renders not produced yet"}>
          {index.data.found ? `${index.data.manifest} lists ${index.data.scenarios.map((s) => s.scenario).join(", ") || "no scenarios"}.`
            : `${index.data.manifest} has not been written yet.`}
        </Empty>
      )}
      {scenario && <ScenarioWall s={scenario} media={media.rows} caseId={scenarioCase?.case.case_id} />}
      {theCase && <CaseWall row={theCase} />}
      {!scenarioParam && !caseParam && index.data && cases.data && (
        <NoSource index={index.data} />
      )}
      {(!index.data || !cases.data) && !index.error && <Loading label="Loading sources" />}
    </div>
  );
}

function SourcePicker({ index, cases, value, onChange }: { index?: ScenarioIndex; cases: CaseListRow[]; value: string;
  onChange: (v: string) => void }) {
  const known = (index?.scenarios ?? []).some((s) => `s:${s.scenario}` === value) || cases.some((c) => `c:${c.case.case_id}` === value);
  return (
    <label className="sp-field" style={{ minWidth: 260 }}>
      <span className="sp-micro">Footage</span>
      <select className="sp-select" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Footage source">
        {!value && <option value="">Choose a scenario or case</option>}
        {value && !known && <option value={value}>{value.slice(2)} (not available)</option>}
        {index?.scenarios.length ? (
          <optgroup label="Scenarios (manifest)">
            {index.scenarios.map((s) => (
              <option key={s.scenario} value={`s:${s.scenario}`}>
                {s.scenario} · {s.title} ({s.rendered}/{s.clip_files.length} rendered)
              </option>
            ))}
          </optgroup>
        ) : null}
        {cases.length ? (
          <optgroup label="Open cases (imported footage)">
            {cases.map((c) => <option key={c.case.case_id} value={`c:${c.case.case_id}`}>{c.case.question.slice(0, 70)}</option>)}
          </optgroup>
        ) : null}
      </select>
    </label>
  );
}

function NoSource({ index }: { index: ScenarioIndex }) {
  return (
    <Empty title={index.found ? "Renders not produced yet" : "Scenario manifest not written yet"}>
      {index.found
        ? "No scenario in the manifest has rendered clips yet, and no case has imported footage. The wall plays them once they exist; nothing is shown in their place."
        : `${index.manifest} is written by the builder (assets/hub/make_cards.py) once the scenario timelines exist. No footage is shown until then.`}
    </Empty>
  );
}

function ScenarioWall({ s, media, caseId }: { s: WallScenario; media: MediaRow[] | null; caseId?: string }) {
  const bySha = useMemo(() => new Map((media ?? []).filter((m) => !m.purged).map((m) => [m.media.sha256, m.media.media_id])), [media]);
  const tiles: WallTile[] = s.clip_files.map((c) => {
    const id = c.sha256 ? bySha.get(c.sha256) : undefined;
    const st = tileState(c, id);
    return {
      key: `${s.scenario}/${c.camera}`, camera: c.camera, osd: hubCamera(c.camera)?.osd_label, mediaId: st === "ready" ? id : undefined,
      noteTitle: st === "not_rendered" ? "Render not produced yet" : "Rendered, not imported",
      note: st === "not_rendered" ? c.file
        : `Import it: npm run seed -- --scenarios ${"ml/evaluation/scenarios/manifest.json"} (the wall plays only footage the backend holds)`,
    };
  });
  const complaint = s.input?.complaint ?? null;
  const subject = s.input?.waybill ?? s.input?.subject_id ?? s.parcel;
  return (
    <section className="sp-stack" style={{ gap: 14 }} aria-labelledby="wall-h">
      <div className="sp-tint" style={{ padding: "14px 18px" }}>
        <p className="sp-micro" id="wall-h">{s.scenario} · {s.title}</p>
        <p className="sp-h3" style={{ margin: "4px 0 0" }}>{complaint ?? (subject ? `Case subject: ${subject}` : "No complaint recorded in case_input.json")}</p>
        <p className="sp-caption" style={{ margin: "4px 0 0" }}>
          {s.input?.question ?? "Question not written yet (case_input.json missing)."}
          {" "}· {s.rendered} of {s.clip_files.length} cameras rendered · clips from {s.clips_dir}
        </p>
        <div className="sp-row" style={{ gap: 8, marginTop: 10 }}>
          {caseId ? <Link className="sp-btn sp-btn-primary sp-btn-sm" href={`/cases/${caseId}`}>Open the case</Link>
            : <span className="sp-caption">No case for {s.scenario} yet: <span className="sp-mono">npm run seed -- --scenarios …</span> creates it.</span>}
        </div>
      </div>
      {s.rendered === 0 ? (
        <Empty title="Renders not produced yet">
          The scenario batch writes {s.clips_dir}/CAM_xx.mp4 ({s.clip_files.map((c) => c.camera).join(", ") || "cameras from case_input.json"}).
          The wall plays them once they are rendered and imported. No footage is shown in their place.
        </Empty>
      ) : media === null ? <Loading label="Matching renders to imported footage" /> : (
        <CameraWall tiles={tiles} title={`${s.scenario} camera wall`} />
      )}
    </section>
  );
}

function CaseWall({ row }: { row: CaseListRow }) {
  const c = row.case;
  const site = useResource<MediaRow[]>(`/v1/sites/${c.site_id}/media`);
  const w0 = c.window ? toMs(c.window.start_utc) : -Infinity;
  const w1 = c.window ? toMs(c.window.end_utc) : Infinity;
  const tiles: WallTile[] = (c.camera_ids ?? []).map((cam) => {
    const m = site.data?.find((x) => !x.purged && x.media.camera_id === cam
      && x.coverage.some((v) => toMs(v.start_utc) <= w1 && toMs(v.end_utc) >= w0));
    const hub = cam.replace(/^cam_/, "");
    return { key: cam, camera: hub, osd: hubCamera(hub)?.osd_label, mediaId: m?.media.media_id,
      noteTitle: "No footage imported", note: "No clip from this camera covers the case window." };
  }).sort((a, b) => Number(!!b.mediaId) - Number(!!a.mediaId) || a.camera.localeCompare(b.camera));
  const withFootage = tiles.filter((t) => t.mediaId);
  return (
    <section className="sp-stack" style={{ gap: 14 }} aria-labelledby="wall-h">
      <div className="sp-tint" style={{ padding: "14px 18px" }}>
        <p className="sp-micro" id="wall-h">Case footage</p>
        <p className="sp-h3" style={{ margin: "4px 0 0" }}>{c.question}</p>
        <p className="sp-caption" style={{ margin: "4px 0 0" }}>{c.target_description} · {withFootage.length} of {tiles.length} cameras in scope have footage in the case window</p>
        <div className="sp-row" style={{ gap: 8, marginTop: 10 }}>
          <Link className="sp-btn sp-btn-primary sp-btn-sm" href={`/cases/${c.case_id}`}>Open the case</Link>
        </div>
      </div>
      {site.loading && <Loading label="Loading footage" />}
      {site.error && <ErrorState error={site.error} what="footage" onRetry={site.reload} />}
      {site.data && (withFootage.length === 0
        ? <Empty title="No footage imported for this case">Import clips in Operator. Nothing is shown in their place.</Empty>
        : <CameraWall tiles={withFootage} title="Case camera wall" />)}
    </section>
  );
}
