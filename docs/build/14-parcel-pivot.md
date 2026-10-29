# Step 14 — Parcel-hub pivot: scan evidence

**Why:** the demo site is now a fictional Malaysian parcel sorting hub (built in Blender) and the missing object is a
parcel. Research basis: [reports/Parcel hub tracking and investigations.md](../../reports/Parcel%20hub%20tracking%20and%20investigations.md).
PRD addendum: see the end of `Spoor_Meta_Hackathon_PRD_v3.md`.

## Done (2026-10-28)

| Plan item | Where | Notes |
|---|---|---|
| 1. `ScanEvent` | `contracts/parcels.py` | Identity-bearing scan record; `scan_real` / `scan_simulated`; read outcomes `read / no_read / no_solve / multi_read`; normalised `ScanEventKind` (visit-opening, in-hub, container, closing, case lifecycle); EPCIS action/bizStep fields; pseudonymous `operator_ref` only; corrections as new events |
| Identifiers | `ParcelIdentifier` | Schemes `s10 / sscc / carrier_waybill / internal / dl_uri / container`; UPU S10 and GS1 check digits computed; a failed check is kept as evidence but never binds identity |
| 2. Containers | `ContainerMembership` + `store/parcels.py` | Versioned, time-bounded parent/child links; `container_chain()` walks parcel → bag → cage → trailer; inherited location labelled **estimated** |
| 3. Relabels | `IdentifierAlias` + `resolve_identity()` | Relabel scans create aliases automatically (`identifiers[0]` = new label) |
| 5. Clock domains | `ClockDomain`, `ClockSync` (+ `clock_domain_id`, `drift_ppm`, `drift_reference`, validity window, anchors, `residual_ms_p95`), `spatial/clock.py: fit_clock()` | Robust offset+drift fit from matched anchor events with mismatch rejection |
| Import | `spoor/scans.py` | JSONL; batch must declare real vs simulated; importer assigns IDs/site/source (never trusted from the file); exact re-imports skipped; container/alias links derived in the same atomic write |
| Visits | `facility_visit()` | `not_visited / open_within_sla / open_overdue / closed_direct / closed_inherited / closed_downstream`; checks aliases, corrections, duplicates, late uploads, missorts, and "bag emptied elsewhere without this parcel" |
| 6 (partial). Graded last seen | `graded_last_seen()` | Fixed scan > handheld scan > video on confirmed/`scan_bound` track; inherited container and candidate video returned separately as leads |
| API | `api/app.py` | `POST /v1/sites/{site}/clock-domains`, `POST /v1/clock-domains/{id}/fit`, `POST /v1/sites/{site}/scans/import`, `GET /v1/sites/{site}/parcels/{scheme}/{value}`; cases accept `identifiers` |

Tests: `tests/test_parcels.py` (21) and `test_api.py::test_parcel_scan_routes`. Full suite: 205 passing.

## Still to do

| # | Item | Notes |
|---|---|---|
| 4 | Automatic `scan_bound` binding | Bind a SAM track to a scan only when exactly one track crosses the read point's camera zone inside the scan's time window; signals `scan_time_residual_ms`, `dims_vs_bbox_consistency`, `ocr_id_match`, `tunnel_image_similarity` |
| 6 | Use graded last-seen in the orchestrator answer and the report | Leads shown separately |
| 7 | Verifier claims `facility_visit_open`, `containment`, `relabel` | Built on `facility_visit()` and `container_chain()` |
| — | Hub topology graph | `HubTopologyEdge(from_zone, to_zone, conveyance, min_transit_s, max_transit_s)` for impossible-jump rejection and next-appearance prediction |
| 8 | Blender hub + scenarios | Control path, no-read rework (parcel circulates the loop, exits at the reject chute), relabel, wrong-bag at bagging, left in chute, phantom containment, mis-load onto wrong truck, look-alike pair, camera outage, removal into blind spot, return-to-sender, parcel mixed up while opening an inbound bag, **parcel stuck on the cover plate between cross-belt carriages** (realistic "fell off the belt"), **two parcels on one carriage** (scanned one, the other reached the chute; some sorters auto-reject doubles). Sorter mis-sorts kept rare; most "wrong place" errors at human steps. Each emits a degraded `scan_simulated` log (clock offsets; 10–20 % no-reads is a **stress test**, not a realistic rate) |
| — | Time-versioned sort plan | Chute → destination mapping with validity windows, so a re-planned chute is not mistaken for a mis-sort |
| — | EPCIS 2.0 JSON-LD export | CCTV observations as `sensorElement` (`rawData` = clip URI) |
