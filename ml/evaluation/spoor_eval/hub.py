"""Parcel-hub evaluation of Spoor's NO-KEY answers (QUEUE F3, PRD §21).

Two phases, in this order:
1. `predict()` runs the real backend in-process (FastAPI TestClient, no model keys, deterministic orchestrator) on
   INPUTS only: hub_spec site plan, synthetic clips, the simulated scan log. One input case per identified parcel.
   It never receives or opens a truth path.
2. `load_truth()` reads the evaluator-only render truth (assets/hub/build/truth: events_truth.jsonl, flow_truth.json)
   AFTER every prediction exists, and `score()` compares.

Scored per case: last-seen correctness (event + time), abstention after the last scan (correct when no imported
camera could have seen the parcel; "missed" when one could, i.e. SAM would have been needed), and false "left the hub".

Headline (review 007 #4): the D scenarios S1-S5 (no-read rework, removal into the blind spot, phantom containment,
mis-load, look-alike pair), one input case per scenario subject, as soon as a scenario has BOTH its renders and its
evaluator truth. On the control flow the scan log is the sorter's own clock, so "last seen 100 %, 0.0 s" is expected and
proves little; it stays as a sanity check and is the headline only as a fallback, with that caveat attached.
"""

import importlib.util
import json
import re
import statistics
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / "frontend" / "scripts" / "seed_nokey.py"
TIME_TOLERANCE_S = 1.0


def _seed_module():
    spec = importlib.util.spec_from_file_location("spoor_seed_nokey", SEED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- phase 1: predictions (runtime inputs only) -----------------------------------------------------------------------


@dataclass
class HubPrediction:
    parcel: str
    case_id: str
    status: str  # answered | abstained | error
    last_seen_time: str | None
    last_seen_event: str | None  # raw event code of the evidence behind "last confirmed"
    last_seen_device: str | None
    last_seen_class: str | None
    later_location_claims: int  # sightings after the last scan (video / candidate); 0 = abstained after the last scan
    left_area: str  # yes | no | unknown, parsed from the stored answer
    no_coverage_intervals: int | None
    answer: str
    latency_s: float
    subject_kind: str = "parcel"


def _left_area(answer: str) -> str:
    m = re.search(r"Leaving the area:\s*(NOT established|supported|contradicted)", answer)
    return {"supported": "yes", "contradicted": "no"}.get(m.group(1), "unknown") if m else "unknown"


def predict(*, scans: Path, clips: Path, spec: Path, clip_start: str, parcels: list[str] | None = None,
            subjects: list[tuple[str, str]] | None = None, window_s: float | None = None, burn_mark: bool = True,
            log=print) -> dict:  # fmt: skip
    """Run Spoor (no keys) on the inputs and return one prediction per subject. Reference data is not an argument.

    `subjects` = [(id, "parcel" | "container")] from a scenario manifest (an input: the customer's waybill or the cage
    the depot asks about); default = every identified parcel in the scan log."""
    from fastapi.testclient import TestClient

    from spoor.api.app import create_app
    from spoor.api.auth import Principal, TokenRegistry
    from spoor.api.services import Services
    from spoor.config import Settings
    from spoor.contracts import Role

    seed = _seed_module()
    work = Path(tempfile.mkdtemp(prefix="spoor_hub_eval_"))
    svc = Services.from_settings(Settings(data_dir=work / "data", model_api_key=None, baseten_api_key=None,
                                          agent_backend="none", rate_limit_per_minute=100_000))  # fmt: skip
    site = {seed.SITE_ID}
    svc.tokens = TokenRegistry({"eval-admin": Principal("eval_admin", Role.SITE_ADMIN, frozenset(site)),
                                "eval-inv": Principal("eval_investigator", Role.INVESTIGATOR, frozenset(site))})
    app = create_app(services=svc)
    admin = TestClient(app, headers={"Authorization": "Bearer eval-admin"})
    inv = TestClient(app, headers={"Authorization": "Bearer eval-inv"})
    got = seed.load_inputs(admin, clips_dir=clips, clip_start=clip_start, scans_path=scans, spec_path=spec,
                           work_dir=work, log=log, burn_mark=burn_mark)  # fmt: skip
    if subjects:
        todo = list(subjects)
    else:
        ids = sorted({i["value"] for r in got["rows"] for i in r.get("identifiers", []) if i["scheme"] == "carrier_waybill"})
        if parcels:
            ids = [p for p in ids if p in set(parcels)]
        todo = [(p, "parcel") for p in ids]
    win = window_s if window_s is not None else 40.0
    raw_of = {s["scan_event_id"]: s for s in admin.get(f"/v1/sites/{seed.SITE_ID}/scans?limit=20000").json()["scans"]}
    preds: list[HubPrediction] = []
    for n, (parcel, kind) in enumerate(todo):
        t = time.perf_counter()
        body = seed.case_body(parcel, got["clips"], clip_start, subject_kind=kind, window_s=win)
        case = inv.post("/v1/cases", json=body).raise_for_status().json()
        cid = case["case"]["case_id"]
        if n == 0:
            seed.import_photo_eyes(admin, cid, got["lines"])
        job_id = inv.post(f"/v1/cases/{cid}/investigate").raise_for_status().json()["job_id"]
        for _ in range(600):
            job = inv.get(f"/v1/jobs/{job_id}").json()
            if job["status"] in ("done", "failed"):
                break
            time.sleep(0.05)
        objs = inv.get(f"/v1/cases/{cid}/last-seen").json()
        ls = objs[0] if objs else {"last_confident": None, "confident": [], "leads": []}
        lc = ls["last_confident"]
        scan = raw_of.get(lc["evidence_id"]) if lc else None
        later = [s for s in ls["confident"] + ls["leads"] if lc and s["time"] > lc["time"]]
        answer = (job.get("result") or {}).get("answer", "") or ""
        m = re.search(r"(\d+) interval\(s\) had no camera coverage", answer)
        preds.append(HubPrediction(
            parcel=parcel, case_id=cid, status=(job.get("result") or {}).get("status", "error") if job["status"] == "done"
            else "error", last_seen_time=lc["time"] if lc else None,
            last_seen_event=(scan or {}).get("raw_code"), last_seen_device=(scan or {}).get("device_id"),
            last_seen_class=lc["class"] if lc else None, later_location_claims=len(later),
            left_area=_left_area(answer), no_coverage_intervals=int(m.group(1)) if m else None, answer=answer,
            latency_s=round(time.perf_counter() - t, 3), subject_kind=kind))  # fmt: skip
    clip_cams = [c.stem for c in got["clips"]]
    return {"predictions": preds, "clip_cameras": clip_cams, "spec": got["spec"], "scans_not_imported": got["skipped"],
            "clip_seconds": seed.clip_seconds(got["clips"]) if got["clips"] else 0.0}


# --- phase 2: evaluator-only truth --------------------------------------------------------------------------------------


@dataclass
class HubTruth:
    parcel: str
    last_event: str | None
    last_event_time: str | None
    final_xy: tuple[float, float] | None
    final_z: float | None
    final_zone: str | None
    inside_building: bool | None
    seen_after_last_event_by: list[str] = field(default_factory=list)  # imported cameras whose FOV it crossed
    track_known: bool = True  # False: the truth has no track for this subject (e.g. a roll cage), abstention not scored


def _inside(pt, poly) -> bool:
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def truth_suffix(scenario: str | None) -> str:
    """File suffix of a scenario's evaluator files: control / S0 = none, S1 = "_S1" (assets/hub/make_cards.py)."""
    return "" if scenario in (None, "S0", "control_flow") else f"_{scenario}"


def load_truth(truth_dir: Path, parcels: list[str], *, spec: dict, clip_cameras: list[str], clip_start: str,
               clip_seconds: float = 30.0, scenario: str | None = None) -> dict[str, HubTruth]:  # fmt: skip
    """Evaluator only. Called after predict() returned. `parcels` may hold container ids (roll cages, bags)."""
    seed = _seed_module()
    suf = truth_suffix(scenario)
    wanted = set(parcels)
    events: dict[str, list[dict]] = {}
    for line in (truth_dir / f"events_truth{suf}.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            for key in {r.get("parcel_id"), r.get("item_id"), r.get("container_id")} & wanted:
                events.setdefault(key, []).append(r)
    flow = json.loads((truth_dir / f"flow_truth{suf}.json").read_text(encoding="utf-8"))
    t0 = datetime.fromisoformat(flow["t0"])
    fps = flow["fps"]
    by_id = {p.get("parcel_id"): p for p in flow["parcels"] if p.get("parcel_id")}
    W, H = spec["building"]["footprint_m"]
    zones = [(z["id"], p) for z in spec["zones"] for p in (z["polygon_m"].values() if isinstance(z["polygon_m"], dict)
                                                            else [z["polygon_m"]])]  # fmt: skip
    cams = {c["id"]: seed.floor_footprint(c) for c in spec["cameras"] if c["id"] in clip_cameras}
    clip_t0 = datetime.fromisoformat(clip_start)
    clip_t1 = clip_t0 + timedelta(seconds=clip_seconds)
    out = {}
    for parcel in parcels:
        evs = sorted(events.get(parcel, []), key=lambda r: r["true_time"])
        last = evs[-1] if evs else None
        p = by_id.get(parcel)
        final_xy = final_z = zone = None
        seen: set[str] = set()
        if p and p.get("track"):
            frames = sorted(p["track"], key=int)
            x, y, z = p["track"][frames[-1]]
            final_xy, final_z = (round(x, 2), round(y, 2)), round(z, 2)
            zone = next((zid for zid, poly in zones if _inside((x, y), poly)), None)
            last_t = datetime.fromisoformat(last["true_time"]) if last else None
            for f in frames:
                tf = t0 + timedelta(seconds=(int(f) - 1) / fps)
                if (last_t and tf <= last_t) or not clip_t0 <= tf <= clip_t1:
                    continue
                fx, fy, _ = p["track"][f]
                seen |= {cid for cid, poly in cams.items() if _inside((fx, fy), poly)}
        known = bool(p and p.get("track"))
        inside = (bool(final_xy) and 0 <= final_xy[0] <= W and 0 <= final_xy[1] <= H) if known else None
        out[parcel] = HubTruth(parcel, last["event"] if last else None, last["true_time"] if last else None, final_xy,
                               final_z, zone, inside, sorted(seen), track_known=known)  # fmt: skip
    return out


# --- scoring --------------------------------------------------------------------------------------------------------


def score(pred: HubPrediction, truth: HubTruth) -> dict:
    err = None
    ok = False
    if pred.last_seen_time and truth.last_event_time:
        err = abs((datetime.fromisoformat(pred.last_seen_time) - datetime.fromisoformat(truth.last_event_time))
                  .total_seconds())  # fmt: skip
        ok = pred.last_seen_event == truth.last_event and err <= TIME_TOLERANCE_S
    abstained_after = pred.later_location_claims == 0 and pred.left_area != "yes"
    if not abstained_after:
        abst = "claimed a later location"
    elif not truth.track_known:
        abst = "not scored: no track for this subject in the reference data"
    elif truth.seen_after_last_event_by:
        abst = "missed: visible on " + ", ".join(truth.seen_after_last_event_by) + " (needs SAM)"
    else:
        abst = "correct: no imported camera saw it after the last scan"
    return {"parcel": pred.parcel, "status": pred.status, "last_seen_correct": ok, "last_seen_time_error_s": err,
            "pred_last_event": pred.last_seen_event, "truth_last_event": truth.last_event,
            "abstained_after_last_scan": abstained_after, "abstention": abst,
            "abstention_correct": abstained_after and truth.track_known and not truth.seen_after_last_event_by,
            "false_left_hub": pred.left_area == "yes" and truth.inside_building is True,
            "truth_final_zone": truth.final_zone, "truth_final_z_m": truth.final_z}  # fmt: skip


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    errs = [r["last_seen_time_error_s"] for r in rows if r["last_seen_time_error_s"] is not None]
    return {
        "n_cases": n,
        "last_seen_accuracy": sum(r["last_seen_correct"] for r in rows) / n if n else None,
        "median_last_seen_time_error_s": statistics.median(errs) if errs else None,
        "abstained_after_last_scan": sum(r["abstained_after_last_scan"] for r in rows),
        "abstention_correct": sum(r["abstention_correct"] for r in rows),
        "abstention_missed_visible": sum(r["abstention"].startswith("missed") for r in rows),
        "false_left_hub": sum(r["false_left_hub"] for r in rows),
    }  # fmt: skip


HEADLINE_SCENARIOS = ("S1", "S2", "S3", "S4", "S5")
CONTROL_CAVEAT = ("Control flow: the scan log is the sorter's own (the WCS is the reference clock), so last seen 100 % "
                  "and a 0.0 s median error are expected and prove little. It is a sanity check, not the headline.")


def plan_suite(manifest: Path, truth_dir: Path) -> dict:
    """Which D scenarios can be scored now: listed in the manifest, renders present (CAM_*.mp4 in the scenario's clips
    folder) AND evaluator files present. Everything else is listed with the reason, never silently dropped."""
    out = {"manifest": str(manifest), "eligible": [], "skipped": [], "control": None}
    if not manifest.exists():
        out["skipped"] = [{"scenario": s, "reason": "scenario manifest not written yet"} for s in HEADLINE_SCENARIOS]
        return out
    items = json.loads(manifest.read_text(encoding="utf-8"))
    listed = {it.get("scenario") for it in items}
    for it in items:
        sc = it.get("scenario")
        if sc not in HEADLINE_SCENARIOS + ("S0",):
            continue
        clips = sorted((manifest.parent / it["clips"]).glob("CAM_*.mp4")) if it.get("clips") else []
        suf = truth_suffix(sc)
        missing = [n for n in (f"scenario_{sc}.json", f"events_truth{suf}.jsonl", f"flow_truth{suf}.json")
                   if not (truth_dir / n).exists()]  # fmt: skip
        if not clips:
            reason = "renders not produced yet"
        elif missing:
            reason = "reference data not written: " + ", ".join(missing)
        else:
            reason = None
        if sc == "S0":
            out["control"] = it if reason is None else None
            continue
        if reason is None:
            out["eligible"].append({**it, "clip_files": [c.name for c in clips]})
        else:
            out["skipped"].append({"scenario": sc, "title": it.get("title"), "reason": reason})
    out["skipped"] += [{"scenario": s, "reason": "not in the manifest"} for s in HEADLINE_SCENARIOS if s not in listed]
    return out


def _suite_result(name: str, label: str, preds: list[HubPrediction], truth: dict[str, HubTruth], inputs: dict,
                  scenario_of: dict[str, dict] | None = None) -> dict:  # fmt: skip
    rows = []
    for p in preds:
        r = score(p, truth[p.parcel])
        if scenario_of:
            r = {"scenario": scenario_of[p.parcel]["scenario"], "title": scenario_of[p.parcel].get("title"),
                 "subject_kind": p.subject_kind, **r}  # fmt: skip
        rows.append(r)
    return {"name": name, "scenario": label, "inputs": inputs, "aggregate": aggregate(rows), "cases": rows,
            "predictions": [asdict(p) for p in preds]}


def run_hub(*, scans: Path, clips: Path, spec: Path, truth_dir: Path, clip_start: str, scenario: str,
            out_dir: Path, parcels: list[str] | None = None, clips_note: str = "", manifest: Path | None = None,
            with_control: bool = True) -> dict:  # fmt: skip
    """Score the no-key answers. With a manifest, the D scenarios that have renders AND reference data are the
    headline; the control flow (S0 renders if scored-ready, else the given clips) is the sanity check / fallback."""
    started = time.perf_counter()
    plan = plan_suite(manifest, truth_dir) if manifest else {"eligible": [], "skipped": [], "control": None,
                                                             "manifest": None}  # fmt: skip
    # phase 1: every prediction, scenarios and control, before any reference file is opened
    scen_runs = []
    for it in plan["eligible"]:
        base = manifest.parent
        sclips = base / it["clips"]
        kind = it.get("subject_kind", "parcel")
        got = predict(scans=base / it["scans"], clips=sclips, spec=spec, clip_start=it["clip_start"],
                      subjects=[(it["parcel"], kind)], burn_mark=False,
                      window_s=max(40.0, _clip_seconds(sclips) + 5))  # fmt: skip
        scen_runs.append((it, got))
    ctrl = None
    if with_control or not scen_runs:
        c = plan.get("control")
        if c:  # the rendered S0 control scenario, every identified parcel
            ctrl_in = {"scans": manifest.parent / c["scans"], "clips": manifest.parent / c["clips"],
                       "clip_start": c["clip_start"], "burn_mark": False, "label": "S0 control (final renders)"}  # fmt: skip
        else:
            ctrl_in = {"scans": scans, "clips": clips, "clip_start": clip_start, "burn_mark": True, "label": scenario}
        got = predict(scans=ctrl_in["scans"], clips=ctrl_in["clips"], spec=spec, clip_start=ctrl_in["clip_start"],
                      parcels=parcels, burn_mark=ctrl_in["burn_mark"])  # fmt: skip
        ctrl = (ctrl_in, got)

    # phase 2: evaluator-only reference data, after every prediction exists
    suites = []
    if scen_runs:
        preds, truth, of, inputs = [], {}, {}, []
        for it, got in scen_runs:
            p = got["predictions"]
            preds += p
            of.update({x.parcel: it for x in p})
            truth.update(load_truth(truth_dir, [x.parcel for x in p], spec=got["spec"], clip_cameras=got["clip_cameras"],
                                    clip_start=it["clip_start"], clip_seconds=got["clip_seconds"] or 30.0,
                                    scenario=it["scenario"]))  # fmt: skip
            inputs.append({"scenario": it["scenario"], "title": it.get("title"), "scan_log": Path(it["scans"]).name,
                           "clips": got["clip_cameras"], "scans_not_imported": got["scans_not_imported"]})
        suites.append(_suite_result("scenarios", "D scenarios " + ", ".join(i["scenario"] for i in inputs), preds, truth,
                                    {"scan_log": "per scenario", "clips": sorted({c for i in inputs for c in i["clips"]}),
                                     "per_scenario": inputs, "clips_note": ""}, of))  # fmt: skip
    if ctrl:
        ctrl_in, got = ctrl
        p = got["predictions"]
        t = load_truth(truth_dir, [x.parcel for x in p], spec=got["spec"], clip_cameras=got["clip_cameras"],
                       clip_start=ctrl_in["clip_start"], scenario="S0")  # fmt: skip
        suites.append(_suite_result("control_flow", ctrl_in["label"], p, t, {
            "scan_log": Path(ctrl_in["scans"]).name, "clips": got["clip_cameras"],
            "scans_not_imported": got["scans_not_imported"], "clips_note": "" if plan.get("control") else clips_note}))

    head = suites[0]
    from_scenarios = head["name"] == "scenarios"
    by_reason: dict[str, list[str]] = {}
    for w in plan["skipped"]:
        by_reason.setdefault(w["reason"], []).append(w["scenario"])
    waiting = "; ".join(f"{', '.join(v)}: {k}" for k, v in by_reason.items())
    caveat = (None if from_scenarios else
              CONTROL_CAVEAT + " The D scenarios (S1-S5) take over the headline once their renders and reference data "
              "exist" + (f" (now: {waiting})." if waiting else "."))  # fmt: skip
    result = {
        "kind": "hub_no_key",
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "variant": "A2-no-key (deterministic orchestrator, no SAM / Spark / LLM agents)",
        "headline": {"source": head["name"], "label": head["scenario"], "caveat": caveat,
                     "scenarios": [i["scenario"] for i in head["inputs"].get("per_scenario", [])],
                     "waiting": plan["skipped"]},
        # the headline suite, flat (the shape the Operator page reads)
        "scenario": head["scenario"], "inputs": head["inputs"], "aggregate": head["aggregate"], "cases": head["cases"],
        "predictions": head["predictions"],
        "suites": [{k: v for k, v in s.items() if k != "predictions"} for s in suites],
        "truth_read_by": "evaluator only (ml/evaluation/spoor_eval/hub.py), after all predictions",
        "note": ("Last seen here can only come from scans: without SAM no footage is analysed. 'missed' means a camera "
                 "with imported footage had the subject in its approximate FOV after the last scan."),
        "runtime_s": round(time.perf_counter() - started, 1),
    }  # fmt: skip
    if not from_scenarios:
        result["control_caveat"] = CONTROL_CAVEAT
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


def _clip_seconds(clips_dir: Path) -> float:
    return _seed_module().clip_seconds(sorted(clips_dir.glob("CAM_*.mp4")))
