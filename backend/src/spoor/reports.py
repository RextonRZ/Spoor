"""Investigation-support report (PRD §22.2-22.3). Built only from stored records; approval is a separate, immutable
record by a reviewer. Hashes support integrity checks; they do not by themselves establish legal chain of custody.

Structure follows how a hub claims / ops team writes up a lost-consignment trace (QUEUE G, req 012): consignment and
scan history first (where it was *scanned*), then the CCTV that was reviewed with each recorder's clock check and
master / working-copy hashes (UK Home Office "Recovery and Acquisition of Video Evidence" v3.0), then continuity of
evidence, and the records a claim usually asks for that this case does not hold (manifest, linehaul loading, POD)."""

import hashlib
import html
import json
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone

from spoor.contracts import (
    Camera,
    CameraCoverage,
    Case,
    ClockSync,
    FloorCalibration,
    Hypothesis,
    MediaAsset,
    MediaAuthorization,
    ObjectInstance,
    RawObservation,
    SensorEvent,
    Site,
    SourceType,
    SpatialEstimate,
    VerifiedFinding,
)
from spoor.store import (
    AgentStep,
    CostEntry,
    EvidenceRequest,
    EvidenceStore,
    coverage_intervals,
    unobserved_intervals,
    visibility_timeline,
)
from spoor.store.parcels import scans_for

DISCLAIMER = ("Investigative decision support; not an official forensic certification or determination of identity "
              "or wrongdoing.")  # fmt: skip
CUSTODY_NOTE = ("Hashes and access logs support integrity checks. They do not by themselves establish a legally "
                "accepted chain of custody.")  # fmt: skip


HUB_LEAVING_KINDS = ("departed_facility", "container_loaded")  # linehaul loading / departure scans


def _scan_history(store: EvidenceStore, objects: list[ObjectInstance], site_id: str) -> tuple[list[dict], set[str]]:
    """Every scan of the consignment's identifiers, chronological, with the gap since the previous scan."""
    keys = {i.key for o in objects for i in o.identifiers if i.usable_for_identity}
    if not keys:
        return [], keys
    rows, prev = [], None
    for ts in scans_for(store, keys, site_id=site_id).scans:
        s = ts.scan
        rows.append({
            "time": _iso(ts.t), "event": s.raw_code or s.event_kind.value, "event_kind": s.event_kind.value,
            "read_point": s.station_id or s.device_id, "device_kind": s.device_kind.value,
            "zone": s.read_point_zone_id, "outcome": s.read_outcome.value,
            "clock": (f"synchronized ±{ts.unc_ms:.0f} ms" if ts.synced and ts.unc_ms is not None
                      else "device time, not synchronized"),
            "late_upload": ts.late_upload, "source": s.source_type.value, "import_batch": s.import_batch,
            "gap_from_previous_s": None if prev is None else round((ts.t_ms - prev) / 1000, 1),
            "scan_event_id": s.scan_event_id,
        })  # fmt: skip
        prev = ts.t_ms
    return rows, keys


def _footage_reviewed(store: EvidenceStore, case: Case) -> list[dict]:
    """Per camera in scope: the original (master) clips covering the case window, their hashes, the working copy, the
    recorder clock check and whether anything was observed in them. Not-analysed footage is listed as such."""
    out = []
    w0 = case.window.start_utc if case.window else None
    w1 = case.window.end_utc if case.window else None
    for cam in case.camera_ids:
        for cov in store.find(CameraCoverage, camera_id=cam):
            if (w0 and cov.end_utc < w0) or (w1 and cov.start_utc > w1) or store.is_invalid(cov.media_id):
                continue
            m = store.get(MediaAsset, cov.media_id)
            auth = store.get(MediaAuthorization, m.authorization_id)
            copies = store.find(MediaAsset, parent_id=m.media_id)
            sync = store.get(ClockSync, cov.sync_id) if store.exists(cov.sync_id) else None
            n_obs = len(store.find(RawObservation, media_id=m.media_id))
            out.append({
                "camera_id": cam, "period_start": _iso(cov.start_utc), "period_end": _iso(cov.end_utc),
                "master_media_id": m.media_id, "master_sha256": m.sha256,
                "working_copy": "; ".join(f"{c.media_id} {c.sha256[:16]}… (converted format: "
                                          f"{c.processing_method or c.kind.value})" for c in copies) or "none",
                "working_copies": [{"media_id": c.media_id, "sha256": c.sha256,
                                    "method": c.processing_method or c.kind.value} for c in copies],
                "clock_check": (f"offset {sync.offset_ms:+.0f} ms ±{sync.uncertainty_ms:.0f} ms ({sync.method})"
                                if sync else "no clock check recorded"),
                "clock_offset_ms": sync.offset_ms if sync else None,
                "clock_uncertainty_ms": sync.uncertainty_ms if sync else None,
                "clock_method": sync.method if sync else None,
                "observations": n_obs,
                "analysed": f"{n_obs} observation(s)" if n_obs else "not analysed (no observations recorded)",
                "label": RECORDING_LABELS.get(auth.recording_kind or "", "Recording type not declared"),
            })  # fmt: skip
    return out


def _continuity(store: EvidenceStore, footage: list[dict], history: list[dict]) -> list[dict]:
    """Audit trail of how each item entered the case: who imported it, when, under which rights statement."""
    rows = []
    for f in footage:
        m = store.get(MediaAsset, f["master_media_id"])
        a = store.get(MediaAuthorization, m.authorization_id)
        rows.append({"item": f"CCTV {_cam(f['camera_id'])} master {m.media_id}", "sha256": m.sha256,
                     "received_by": a.uploader, "received_at": _iso(a.recorded_at), "purpose": a.purpose,
                     "rights": a.rights_statement, "retain_until": _iso(a.retention_until)})
    for batch in sorted({h["import_batch"] for h in history}):
        n = sum(h["import_batch"] == batch for h in history)
        src = next(h["source"] for h in history if h["import_batch"] == batch)
        rows.append({"item": f"scan log batch {batch} ({n} event(s) for this consignment)", "sha256": None,
                     "received_by": "scan import route", "received_at": None, "purpose": SCAN_SOURCE_LABELS.get(src, src),
                     "rights": None, "retain_until": None})
    return rows


def _sources_used(footage: list[dict], history: list[dict]) -> list[dict]:
    """Every input this report rests on: the CCTV masters reviewed and the scan-log batches (review 012 #4)."""
    rows = [{"kind": "CCTV master (original as received)", "item": f"{_cam(f['camera_id'])} · {f['master_media_id']}",
             "sha256": f["master_sha256"], "label": f["label"]} for f in footage]
    for batch in sorted({h["import_batch"] for h in history}):
        src = next(h["source"] for h in history if h["import_batch"] == batch)
        n = sum(h["import_batch"] == batch for h in history)
        rows.append({"kind": "Scan log batch", "item": f"{batch} · {n} scan(s) of this consignment", "sha256": None,
                     "label": SCAN_SOURCE_LABELS.get(src, src)})
    return rows


SCAN_SOURCE_LABELS = {"scan_simulated": "Simulated scan log (scan_simulated)", "scan_real": "Scan log from the sorter / WMS (scan_real)"}


def _cam(camera_id: str | None) -> str:
    """'cam_CAM_01' (record id) -> 'CAM_01' (what the recorder and the OSD call it)."""
    return camera_id.removeprefix("cam_") if camera_id else "none"


def _records_not_held(history: list[dict]) -> list[dict]:
    """What a claims team normally asks for and whether this case holds it (stated, never assumed)."""
    leaving = [h for h in history if h["event_kind"] in HUB_LEAVING_KINDS]
    return [
        {"record": "Collection / handover manifest (proof the courier received the consignment)",
         "held": "no: not imported for this case"},
        {"record": "Linehaul loading or departure scan (consignment, bag or cage loaded out of the hub)",
         "held": (f"yes: {len(leaving)} scan(s), last at {leaving[-1]['read_point']} {leaving[-1]['time']}" if leaving
                  else "no: none among the imported scans")},
        {"record": "Proof of delivery (POD: signature, photo or ID at delivery)",
         "held": "no: delivery records are outside the hub; not imported"},
    ]  # fmt: skip


RECORDING_LABELS = {
    "staged_event": "Real recording of staged event",
    "real_incident": "Real recording of an actual incident",
    "synthetic_test": "Synthetic test footage",
}


def content_fingerprint(report: dict) -> str:
    """Hash of the evidence content only (generation time excluded) — detects any change since a draft."""
    return canonical_sha256({k: v for k, v in report.items() if k != "generated_at"})


def _iso(dt) -> str | None:
    return dt.isoformat(timespec="milliseconds") if dt else None


def canonical_sha256(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _legal_context(store: EvidenceStore, site_id: str) -> dict | None:
    """The latest web-grounded Malaysian context for this site (J3): background for the reader, never evidence."""
    from spoor.grounding import latest_legal_context

    rec = latest_legal_context(store, site_id)
    return rec.model_dump(mode="json", include={"legal_context_id", "model", "answers", "sources", "searches",
                                                "retrieved_at", "label", "content_sha256"}) if rec else None  # fmt: skip


def build_report(store: EvidenceStore, case_id: str, *, site: Site, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    case = store.get(Case, case_id)
    invalid = store.invalid_ids()
    findings = store.find(VerifiedFinding, case_id=case_id)
    hypotheses = store.find(Hypothesis, case_id=case_id)
    objects = store.find(ObjectInstance, case_id=case_id)

    obs_ids = sorted({o for f in findings for o in f.observation_ids}
                     | {o for h in hypotheses for o in h.support_observation_ids + h.against_observation_ids})
    observations = [store.get(RawObservation, o) for o in obs_ids if store.exists(o)]
    media_ids = sorted({o.source_frame.media_id for o in observations if o.source_frame})
    media = {m: store.get(MediaAsset, m) for m in media_ids if store.exists(m)}
    auths = {a: store.get(MediaAuthorization, a) for a in {m.authorization_id for m in media.values()}}
    cams = sorted({o.camera_id for o in observations if o.camera_id})
    est_ids = sorted({e for f in findings for e in f.spatial_estimate_ids})
    estimates = [store.get(SpatialEstimate, e) for e in est_ids if store.exists(e)]
    calib_ids = sorted({e.calibration_id for e in estimates if e.calibration_id})
    zones = {z.zone_id: z.name for z in site.zones}

    unknowns = []
    site_cams = {c.camera_id for c in store.find(Camera, site_id=case.site_id)}
    coverage_end = max((b for _, b, _ in coverage_intervals(store, site_cams)), default=None)
    for obj in objects:
        spans = [s for s in visibility_timeline(store, obj.object_instance_id) if s.observation_ids]
        if spans and coverage_end is not None:
            # Unknowns are reported up to the end of recorded coverage, not "until now".
            for g in unobserved_intervals(store, obj.object_instance_id, spans[0].start_ms,
                                          max(coverage_end, spans[-1].end_ms)):
                unknowns.append({"object": obj.label, "start": datetime.fromtimestamp(g.start_ms / 1000, UTC),
                                 "end": datetime.fromtimestamp(g.end_ms / 1000, UTC), "reason": g.reason,
                                 "covering_cameras": g.covering_camera_ids})  # fmt: skip

    history, keys = _scan_history(store, objects, case.site_id)
    footage = _footage_reviewed(store, case)
    steps = store.find(AgentStep, case_id=case_id)
    costs = store.find(CostEntry, case_id=case_id)
    sensors = store.find(SensorEvent, site_id=case.site_id)
    report = {
        "title": f"Spoor investigation-support report · {case.target_description}",
        "disclaimer": DISCLAIMER,
        "custody_note": CUSTODY_NOTE,
        "generated_at": _iso(now),
        "case": {"case_id": case.case_id, "question": case.question, "target": case.target_description,
                 "cameras_in_scope": case.camera_ids, "created_by": case.created_by,
                 "created_at": _iso(case.created_at),
                 "window": ({"start": _iso(case.window.start_utc), "end": _iso(case.window.end_utc)}
                            if case.window else None)},
        "claim": {"claim_reference": case.claim_reference, "complaint": case.complaint,
                  "reported_at": _iso(case.reported_at)},
        "case_revision_id": (h.case_revision_id if (h := store.head_revision(case_id)) else None),
        "consignment": {"identifiers": sorted(keys), "scan_events": len(history),
                        "last_scan": history[-1] if history else None},
        "scan_history": history,
        "footage_reviewed": footage,
        "sources_used": _sources_used(footage, history),
        "continuity": _continuity(store, footage, history),
        "records_not_held": _records_not_held(history),
        "sources": [{
            "media_id": m.media_id, "camera_id": m.camera_id, "kind": m.kind.value, "sha256": m.sha256,
            "original_filename": m.original_filename, "flags": m.probe.flags if m.probe else [],
            "rights": auths[m.authorization_id].rights_statement, "purpose": auths[m.authorization_id].purpose,
            "label": RECORDING_LABELS.get(auths[m.authorization_id].recording_kind, "Recording type not declared")
            if m.kind.value == "original" else m.kind.value,
        } for m in media.values()],
        "clocks": [{"camera_id": s.camera_id, "offset_ms": s.offset_ms, "uncertainty_ms": s.uncertainty_ms,
                    "method": s.method} for c in cams for s in store.find(ClockSync, camera_id=c)],
        "calibrations": [{
            "calibration_id": c.calibration_id, "camera_id": c.camera_id, "state": c.rig_state.value,
            "holdout_median_m": c.holdout_error_median_m, "holdout_p95_m": c.holdout_error_p95_m,
            "invalidated": c.calibration_id in invalid,
        } for c in (store.get(FloorCalibration, i) for i in calib_ids)],
        "direct_observations": sorted([{
            "observation_id": o.observation_id, "time": _iso(o.source_frame.normalized_utc),
            "time_uncertainty_ms": o.source_frame.time_uncertainty_ms, "camera_id": o.camera_id,
            "media_id": o.source_frame.media_id, "frame_index": o.source_frame.frame_index,
            "media_sha256": media[o.source_frame.media_id].sha256 if o.source_frame.media_id in media else None,
            "label": o.label, "model": o.provenance.model if o.provenance else None,
            "quality_flags": o.quality_flags, "invalidated": o.observation_id in invalid,
        } for o in observations], key=lambda r: r["time"] or ""),
        "findings": [{"finding_id": f.finding_id, "statement": f.statement, "status": f.verification_status.value,
                      "observation_ids": f.observation_ids, "limitations": f.limitations,
                      "verified_by": f.verified_by.id, "invalidated": f.finding_id in invalid}
                     for f in findings],
        "spatial_estimates": [{
            "estimate_id": e.estimate_id, "mode": e.spatial_mode.value, "floor_xy_m": e.floor_xy_m,
            "uncertainty_radius_m": e.uncertainty_radius_m, "zone": zones.get(e.zone_id, e.zone_id),
            "method": e.method, "calibration_id": e.calibration_id, "status": e.status,
        } for e in estimates],
        "unknown_intervals": unknowns,
        "hypotheses": [{
            "hypothesis_id": h.hypothesis_id, "claim": h.claim, "status": h.status.value,
            "proposed_by": f"{h.proposed_by.kind.value}:{h.proposed_by.id} ({h.proposed_by.model or '-'})",
            "support": h.support_observation_ids, "against": h.against_observation_ids,
            "missing_evidence": h.missing_evidence,
            "history": [{"to": c.to_status.value, "actor": f"{c.actor.kind.value}:{c.actor.id}", "reason": c.reason,
                         "at": _iso(c.at)} for c in store.status_history(h.hypothesis_id)],
        } for h in hypotheses],
        "evidence_requests": [{"reason": r.reason, "camera_id": r.camera_id, "start": _iso(r.start_utc),
                               "end": _iso(r.end_utc)} for r in store.find(EvidenceRequest, case_id=case_id)],
        "processing": {
            "agent_steps": dict(Counter(f"{s.role}:{s.kind}" for s in steps)),
            "models": sorted({c.model for c in costs}),
            "model_calls": len(costs), "cache_hits": sum(c.cache_hit for c in costs),
            "tokens": {"input": sum(c.input_tokens for c in costs), "output": sum(c.output_tokens for c in costs)},
        },
        "legal_context": _legal_context(store, site.site_id),
        "simulated_inputs": [{"sensor_event_id": s.sensor_event_id, "kind": s.kind.value, "device_id": s.device_id,
                              "label": "Simulated input"} for s in sensors
                             if s.source_type == SourceType.SENSOR_SIMULATED],
    }  # fmt: skip
    return json.loads(json.dumps(report, default=str))


def manifest(report: dict) -> dict:
    return {
        "report_sha256": canonical_sha256(report),
        "sources": [{"media_id": s["media_id"], "sha256": s["sha256"]} for s in report["sources"]],
        "algorithm": "SHA-256 over canonical JSON (sorted keys, compact separators)",
        "note": CUSTODY_NOTE,
    }


# Report times are shown in the hub's local time (review 012 #2). Malaysia keeps UTC+08:00 all year (no DST), so a
# fixed offset is exact; stored records and the JSON download keep ISO 8601 with their offset.
REPORT_TZ = timezone(timedelta(hours=8), "MYT")
TZ_NOTE = ("All times are Malaysia Time (MYT, UTC+08:00). Stored records and the JSON download keep ISO 8601 times "
           "with their UTC offset.")  # fmt: skip
WORKING_COPY_METHODS = {"proxy_h264_v1": "H.264"}
# Review 012 #7, read in the Laws of Malaysia reprint (Act 56, online updated text as at 1 Dec 2012), s.90A(2) and (4).
# Only what that text says; the PDPA 2010 retention wording could not be read from a primary source, so it is not cited.
MY_EVIDENCE_NOTE = ("Malaysia: under the Evidence Act 1950 (Act 56) s.90A(2), that a document was produced by a computer "
                    "in the course of its ordinary use may be proved by a certificate signed by the person responsible "
                    "for the management of that computer's operation; s.90A(4) then presumes it was working properly. "
                    "This report is not that certificate: for CCTV recorders and scan systems it would come from their "
                    "operator. Text as in the Laws of Malaysia reprint as at 1 December 2012.")  # fmt: skip
MONO_KEYS = {"master_sha256", "sha256", "media_id", "observation_ids", "calibration_id"}


def fmt_time(iso: str | None, *, date: bool = True) -> str:
    """'2026-10-28T06:32:07.912+00:00' -> '28 Oct 2026, 14:32:07.9 MYT' (tenths of a second, like the scan log)."""
    if not iso:
        return "not recorded"
    t = datetime.fromisoformat(iso).astimezone(REPORT_TZ)
    clock = f"{t:%H:%M:%S}.{t.microsecond // 100_000}"
    return f"{t.day} {t:%b %Y}, {clock} MYT" if date else f"{clock} MYT"


def fmt_value(v) -> str:
    if v is None or v == "" or v == []:
        return "not recorded"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, list):
        return ", ".join(fmt_value(x) for x in v)
    return str(v)


def _clock_cell(f: dict, notes: list[str]) -> str:
    """One short cell per recorder; the long method text goes once into a numbered footnote (review 012 #6)."""
    if "clock_method" not in f:  # reports stored before review 012 kept only the sentence
        return f.get("clock_check") or "not recorded"
    method, unc, off = f["clock_method"], f.get("clock_uncertainty_ms"), f.get("clock_offset_ms")
    if method is None:
        return "no clock check recorded"
    if method not in notes:
        notes.append(method)
    mark = notes.index(method) + 1
    span = f"±{unc / 1000:g} s" if unc >= 1000 else f"±{unc:.0f} ms"
    if method.upper().startswith("UNVERIFIED"):
        return f"{span} · unverified, uploader-declared [{mark}]"
    offset = f"{off / 1000:+.1f} s" if abs(off) >= 1000 else f"{off:+.0f} ms"
    return f"{offset} {span} [{mark}]"


def _working_copy_cell(f: dict) -> str:
    if "working_copies" not in f:  # stored before review 012
        return f.get("working_copy") or "none"
    copies = f["working_copies"]
    if not copies:
        return "none"
    return "; ".join(f"{c['sha256'][:16]}… · converted format ({WORKING_COPY_METHODS.get(c['method'], c['method'])})"
                     for c in copies)  # fmt: skip


def _secs(v) -> str:
    return "not recorded" if v is None else f"{v:g} s"


def _table(rows: list[dict], cols: list[tuple], empty: str) -> str:
    """cols = (header, key) or (header, key, formatter). Empty sections say why in words, once."""
    e = html.escape
    if not rows:
        return f"<p class=muted>{e(empty)}</p>"
    head = "".join(f"<th>{e(c[0])}</th>" for c in cols)
    body = "".join("<tr>" + "".join(
        f"<td{' class=mono' if c[1] in MONO_KEYS else ''}>{e((c[2] if len(c) > 2 else fmt_value)(r.get(c[1])))}</td>"
        for c in cols) + "</tr>" for r in rows)  # fmt: skip
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _kv(rows: list[tuple[str, str]]) -> str:
    e = html.escape
    return "<dl class=kv>" + "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in rows) + "</dl>"


def _legal_html(ctx: dict | None) -> str:
    e = html.escape
    if not ctx:
        return ("<p class=muted>Not retrieved: web-grounded context needs the Model API key; a site admin runs it from "
                "the Operator page. The Evidence Act note under the footnotes is from the Laws of Malaysia reprint.</p>")
    out = []
    for a in ctx["answers"]:
        body = " ".join(f"{e(s['text'])}" + "".join(f"<sup>[{n}]</sup>" for n in s["sources"]) for s in a["sentences"])
        dropped = f" <span class=muted>({a['dropped_uncited']} uncited sentence(s) left out)</span>" if a["dropped_uncited"] else ""
        out.append(f"<p><b>{e(a['question'])}</b><br>{body or '<span class=muted>No cited answer.</span>'}{dropped}</p>")
    srcs = "".join(f"<li>[{s['n']}] {e(s['title'])} · {e(s['domain'])}{' · official' if s['official'] else ''}<br>"
                   f"<span class=muted>{e(s['url'])}</span></li>" for s in ctx["sources"])  # fmt: skip
    return ("".join(out) + f"<ol class=plain>{srcs}</ol>"
            + f"<p class=muted>Retrieved {e(fmt_time(ctx['retrieved_at']))} by {e(ctx['model'])} with web search "
              f"({ctx['searches']} searches). {e(ctx['label'])} Record {e(ctx['legal_context_id'])}, "
              f"SHA-256 {e(ctx['content_sha256'])}.</p>")


def render_html(report: dict, *, status: str, approved_by: str | None = None, second_approver: bool = True) -> str:
    """The document a claims team or investigator hands over (review 012): human labels, one time zone (MYT),
    the complaint the case started from, the sources actually used, and empty states said once in words."""
    e, table, kv = html.escape, _table, _kv
    c = report["case"]
    claim = report.get("claim") or {}
    cons = report.get("consignment", {})
    waybills = [i.split(":", 1)[1] for i in cons.get("identifiers", []) if i.startswith("carrier_waybill:")]
    others = [i for i in cons.get("identifiers", []) if not i.startswith("carrier_waybill:")]
    window = c.get("window")
    clock_notes: list[str] = []
    footage = [{**f, "camera": _cam(f["camera_id"]), "clock_cell": _clock_cell(f, clock_notes),
                "copy_cell": _working_copy_cell(f),
                "period": f"{fmt_time(f['period_start'])} → {fmt_time(f['period_end'], date=False)}"}
               for f in report.get("footage_reviewed", [])]  # fmt: skip
    proc = report["processing"]
    # four-eyes is a site setting (review F-047..051): off on the one-user demo site, where a shared report is a summary
    banner = (f"APPROVED by {e(approved_by)}" if status == "approved" else "DRAFT · not reviewer-approved" if second_approver
              else "Investigation summary · decision support")  # fmt: skip
    complaint = (f"<blockquote>{e(claim['complaint'])}</blockquote>" if claim.get("complaint")
                 else "<p class=muted>Not recorded when the case was opened.</p>")  # fmt: skip
    cited = ", ".join(f"{_cam(s['camera_id'])} {s['media_id']}" for s in report["sources"])
    footnotes = [TZ_NOTE] + [f"[{i}] Recorder clock check: {n}" for i, n in enumerate(clock_notes, 1)] + [MY_EVIDENCE_NOTE]

    sections = [
        "<h2>Complaint</h2>" + kv([
            ("Case reference", c["case_id"]),
            ("Claim reference", claim.get("claim_reference") or "not recorded"),
            ("Waybill", ", ".join(waybills) or "none"),
            ("Date reported", fmt_time(claim.get("reported_at")) if claim.get("reported_at") else "not recorded"),
            ("Opened by", f"{c['created_by']}, {fmt_time(c['created_at'])}"),
        ]) + "<p><b>Customer's complaint, as reported:</b></p>" + complaint,
        "<h2>Scope</h2>" + kv([
            ("Question", c["question"]),
            ("Target", c["target"]),
            ("Other identifiers (bag / cage)", ", ".join(others) or "none"),
            ("Cameras in scope", ", ".join(_cam(x) for x in c.get("cameras_in_scope", [])) or "none"),
            ("Case window", f"{fmt_time(window['start'])} → {fmt_time(window['end'], date=False)}" if window
             else "not set"),
            ("Report", f"revision {report['case_revision_id'] or 'none'} · generated {fmt_time(report['generated_at'])}"),
        ]),
        "<h2>Scan history (where the consignment was scanned, not where it went)</h2>" + table(
            report.get("scan_history", []),
            [("Time", "time", fmt_time), ("Scan", "event"), ("Read point", "read_point"), ("Device", "device_kind"),
             ("Zone", "zone"), ("Result", "outcome"), ("Device clock", "clock"),
             ("Gap since previous scan", "gap_from_previous_s", _secs), ("Uploaded late", "late_upload"),
             ("Source", "source", lambda v: SCAN_SOURCE_LABELS.get(v, fmt_value(v)))],
            "No scans of this consignment's identifiers were imported."),
        "<h2>Verified findings</h2>" + table(
            report["findings"],
            [("Statement", "statement"), ("Status", "status"), ("Observations", "observation_ids"),
             ("Limitations", "limitations"), ("Invalidated", "invalidated")],
            "No verified findings: nothing has been observed in the footage yet (tracking needs SAM)."),
        "<h2>Direct observations (chronological)</h2>" + table(
            report["direct_observations"],
            [("Time", "time", fmt_time), ("Clock uncertainty", "time_uncertainty_ms",
                                          lambda v: "not recorded" if v is None else f"±{v:g} ms"),
             ("Camera", "camera_id", _cam), ("Master", "media_id"), ("Frame", "frame_index"), ("Label", "label"),
             ("Quality flags", "quality_flags"), ("Invalidated", "invalidated")],
            "No direct observations recorded."),
        "<h2>Spatial estimates (estimated, not measured)</h2>" + table(
            report["spatial_estimates"],
            [("Mode", "mode"), ("Zone", "zone"), ("Floor position (m)", "floor_xy_m"),
             ("Uncertainty radius (m)", "uncertainty_radius_m"), ("Method", "method"),
             ("Calibration", "calibration_id")],
            "No spatial estimates."),
        "<h2>Unknown intervals</h2>" + table(
            report["unknown_intervals"],
            [("Object", "object"), ("From", "start", fmt_time), ("To", "end", fmt_time), ("Reason", "reason"),
             ("Cameras covering", "covering_cameras", lambda v: fmt_value([_cam(x) for x in v or []]))],
            "None computed: unknown intervals start from the first observation, and there is none yet."),
        "<h2>CCTV reviewed (master = original as received; working copy = converted format)</h2>" + table(
            footage,
            [("Camera", "camera"), ("From / To", "period"), ("Master SHA-256", "master_sha256"),
             ("Working copy", "copy_cell"), ("Clock check", "clock_cell"), ("Analysed", "analysed"),
             ("Footage type", "label")],
            "No CCTV covering the case window was imported for the cameras in scope."),
        "<h2>Hypotheses considered</h2>" + table(
            report["hypotheses"],
            [("Claim", "claim"), ("Status", "status"), ("Proposed by", "proposed_by"),
             ("Missing evidence", "missing_evidence")],
            "No hypotheses recorded."),
        "<h2>Outstanding evidence requests</h2>" + table(
            report["evidence_requests"],
            [("Reason", "reason"), ("Camera", "camera_id", _cam), ("From", "start", fmt_time), ("To", "end", fmt_time)],
            "No outstanding evidence requests."),
        "<h2>Continuity of evidence (audit trail)</h2>" + table(
            report.get("continuity", []),
            [("Item", "item"), ("SHA-256", "sha256"), ("Received by", "received_by"),
             ("Received", "received_at", fmt_time), ("Purpose", "purpose"), ("Rights", "rights"),
             ("Retain until", "retain_until", fmt_time)],
            "No items entered the case."),
        "<h2>Records a claim usually needs</h2>" + table(
            report.get("records_not_held", []), [("Record", "record"), ("Held", "held")], "None listed."),
        "<h2>Malaysian context (from the web, cited and dated)</h2>" + _legal_html(report.get("legal_context")),
        "<h2>Sources used</h2>" + table(
            report.get("sources_used", []),
            [("Kind", "kind"), ("Item", "item"), ("SHA-256", "sha256"), ("Label", "label")],
            "No sources: nothing was imported for this case.")
        + f"<p class=muted>Cited by findings: {e(cited or 'none (no verified observation cites a frame yet)')}.</p>",
        "<h2>Clocks and calibration</h2>" + table(
            report["clocks"],
            [("Camera", "camera_id", _cam), ("Offset", "offset_ms", lambda v: f"{v:+.0f} ms"),
             ("Uncertainty", "uncertainty_ms", lambda v: f"±{v:.0f} ms"), ("Method", "method")],
            "No clock corrections beyond the recorder clock checks under CCTV reviewed.") + table(
            report["calibrations"],
            [("Calibration", "calibration_id"), ("Camera", "camera_id", _cam), ("State", "state"),
             ("Hold-out median (m)", "holdout_median_m"), ("Hold-out p95 (m)", "holdout_p95_m"),
             ("Invalidated", "invalidated")],
            "No floor calibration was used (no spatial estimates)."),
        "<h2>Processing</h2>" + kv([
            ("Models used", ", ".join(proc["models"]) or "none"),
            ("Model calls", f"{proc['model_calls']} ({proc['cache_hits']} from cache)"),
            ("Agent steps", str(sum(proc["agent_steps"].values()))),
            ("Tokens", f"{proc['tokens']['input']} in · {proc['tokens']['output']} out"),
        ]) + f"<details><summary>Processing record (JSON appendix)</summary><pre>{e(json.dumps(proc, indent=2))}"
             "</pre></details>",
    ]  # fmt: skip
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(report['title'])}</title>
<style>body{{font:14px/1.5 system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#111}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td,th{{border:1px solid #ccc;padding:4px 6px;text-align:left;
vertical-align:top;font-size:12px}}th{{background:#f4f4f4}}.mono{{font-family:ui-monospace,monospace;font-size:11px;
word-break:break-all}}.banner{{padding:8px;border:2px solid #333;font-weight:600}}.muted{{color:#555}}ol.plain{{list-style:none;padding-left:0}}
.disclaimer{{background:#fff4d6;padding:8px;border-left:4px solid #c90}}.kv{{display:grid;
grid-template-columns:max-content 1fr;gap:2px 16px;margin:8px 0}}.kv dt{{color:#555}}.kv dd{{margin:0}}
blockquote{{margin:4px 0;padding:6px 10px;border-left:3px solid #999;background:#f7f7f7}}
footer{{margin-top:24px;border-top:1px solid #ccc;font-size:12px;color:#444}}
details pre{{font-size:11px;background:#f7f7f7;padding:8px;overflow:auto}}</style></head><body>
<h1>{e(report['title'])}</h1><p class=banner>{banner}</p>
<p class=disclaimer>{e(report['disclaimer'])}<br>{e(report['custody_note'])}</p>
{"".join(sections)}
<footer>{"".join(f"<p>{e(n)}</p>" for n in footnotes)}</footer>
</body></html>"""  # fmt: skip
