"""Investigation-support report (PRD §22.2-22.3). Built only from stored records; approval is a separate, immutable
record by a reviewer. Hashes support integrity checks; they do not by themselves establish legal chain of custody."""

import hashlib
import html
import json
from collections import Counter
from datetime import UTC, datetime

from spoor.contracts import (
    Camera,
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

DISCLAIMER = ("Investigative decision support; not an official forensic certification or determination of identity "
              "or wrongdoing.")  # fmt: skip
CUSTODY_NOTE = ("Hashes and access logs support integrity checks. They do not by themselves establish a legally "
                "accepted chain of custody.")  # fmt: skip


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

    steps = store.find(AgentStep, case_id=case_id)
    costs = store.find(CostEntry, case_id=case_id)
    sensors = store.find(SensorEvent, site_id=case.site_id)
    report = {
        "title": f"Spoor investigation-support report — {case.target_description}",
        "disclaimer": DISCLAIMER,
        "custody_note": CUSTODY_NOTE,
        "generated_at": _iso(now),
        "case": {"case_id": case.case_id, "question": case.question, "target": case.target_description,
                 "cameras_in_scope": case.camera_ids, "created_by": case.created_by,
                 "created_at": _iso(case.created_at)},
        "case_revision_id": (h.case_revision_id if (h := store.head_revision(case_id)) else None),
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


def render_html(report: dict, *, status: str, approved_by: str | None = None) -> str:
    e = html.escape

    def table(rows: list[dict], cols: list[str]) -> str:
        if not rows:
            return "<p class=muted>None.</p>"
        head = "".join(f"<th>{e(c)}</th>" for c in cols)
        body = "".join("<tr>" + "".join(f"<td>{e(str(r.get(c, '')))}</td>" for c in cols) + "</tr>" for r in rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    c = report["case"]
    banner = f"APPROVED by {e(approved_by)}" if status == "approved" else "DRAFT — not reviewer-approved"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(report['title'])}</title>
<style>body{{font:14px/1.5 system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#111}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td,th{{border:1px solid #ccc;padding:4px 6px;text-align:left;
vertical-align:top;font-size:12px}}.banner{{padding:8px;border:2px solid #333;font-weight:600}}.muted{{color:#666}}
.disclaimer{{background:#fff4d6;padding:8px;border-left:4px solid #c90}}</style></head><body>
<h1>{e(report['title'])}</h1><p class=banner>{banner}</p>
<p class=disclaimer>{e(report['disclaimer'])}<br>{e(report['custody_note'])}</p>
<h2>Scope</h2><p><b>Question:</b> {e(c['question'])}<br><b>Target:</b> {e(c['target'])}<br>
<b>Case:</b> {e(c['case_id'])} · revision {e(str(report['case_revision_id']))} · generated {e(report['generated_at'])}</p>
<h2>Verified findings</h2>{table(report['findings'], ['statement', 'status', 'observation_ids', 'limitations',
                                                       'invalidated'])}
<h2>Direct observations (chronological)</h2>{table(report['direct_observations'], ['time', 'time_uncertainty_ms',
    'camera_id', 'media_id', 'frame_index', 'label', 'quality_flags', 'invalidated'])}
<h2>Spatial estimates (estimated, not measured)</h2>{table(report['spatial_estimates'], ['mode', 'zone',
    'floor_xy_m', 'uncertainty_radius_m', 'method', 'calibration_id'])}
<h2>Unknown intervals</h2>{table(report['unknown_intervals'], ['object', 'start', 'end', 'reason',
                                                                 'covering_cameras'])}
<h2>Hypotheses considered</h2>{table(report['hypotheses'], ['claim', 'status', 'proposed_by', 'missing_evidence'])}
<h2>Outstanding evidence requests</h2>{table(report['evidence_requests'], ['reason', 'camera_id', 'start', 'end'])}
<h2>Sources</h2>{table(report['sources'], ['media_id', 'camera_id', 'label', 'sha256', 'flags', 'rights'])}
<h2>Clocks and calibration</h2>{table(report['clocks'], ['camera_id', 'offset_ms', 'uncertainty_ms', 'method'])}
{table(report['calibrations'], ['calibration_id', 'camera_id', 'state', 'holdout_median_m', 'holdout_p95_m',
                                'invalidated'])}
<h2>Processing</h2><pre>{e(json.dumps(report['processing'], indent=2))}</pre>
</body></html>"""  # fmt: skip
