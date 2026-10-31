# Request 012 — Frontend: QUEUE G, the investigator workflow made authentic (claims trace, CCTV retrieval, terms)

From the frontend agent. (Request 011, induction line B, is still waiting for review.)

Each item below gives what the research showed, then what we changed, with sources. Brands in the sources are real
companies; the app still shows only CONTOH Express.

## 1. Changed since last request

### G1 · Report = a lost-consignment trace, in the order a claims team works
- **Research showed:**
  - A lost-parcel complaint starts from the tracking / waybill number. The courier asks for it first, plus a
    description and proof of purchase, and gives a case reference.
  - An investigation starts at the last known scan and works forward. Investigators read the scan history for gaps,
    and know that a hub can process a parcel without scanning it at every step.
  - A courier manifest is "a shipment list that acts as proof of collection", signed by the courier at pickup.
  - Proof of delivery (POD) is a signature, photo or ID scan at delivery.
  - Linehaul is the trunk movement between hubs.
- **What we changed:** the backend report (`backend/src/spoor/reports.py`, rendered on the Report page) has four new
  parts:
  - *Consignment identifiers* in the scope.
  - *Scan history (where the consignment was scanned, not where it went)*: every scan in time order, with read point,
    device kind, clock state (synchronized ±x ms, or device time), late upload, source, and the gap since the previous
    scan.
  - *Continuity of evidence* (see G2).
  - *Records a claim usually needs*: collection / handover manifest, linehaul loading or departure scan, and POD. Each
    is stated as held or not held, from the imported records only. Here none are held, and the report says so.

  Backend test added to `test_parcel_scan_routes`. It also shows why the clock column matters: two scans 300 s apart on
  their device clocks are 293 s apart once the tunnel's WCS clock fit is applied.
- **Sources:**
  - https://blog.ninjavan.co/en-my/thrown-package-dont-stay-silent-how-to-report-rough-deliveries-by-malaysian-couriers
    (Ninja Van MY: tracking number + description, NinjaChat / Contact Us)
  - https://parceldaily.com/?p=6220 (secondary: proof of purchase, tracking ID, ask for a case reference)
  - https://www.indiehackers.com/post/what-to-do-when-a-courier-company-loses-your-package-HW5BeZs57ov69hALVKtr (trace
    from the last known scan; hubs may not scan every step)
  - https://www.shipaid.com/blogs/ecommerce-shipping/package-lost-between-ups-and-usps-a-merchant-s-guide (a manifest
    scan can be logical, not physical)
  - https://blog.easyparcel.com/my/3-domestic-delivery-documents/ (MY: AWB, commercial invoice, courier manifest = proof
    of collection, signed by the courier)
  - https://cs-learning-hub.app.shipsy.ai/reference/glossary (POD, linehaul)

### G2 · CCTV retrieval the way evidence units do it: clock check, master / working copy, continuity
- **Research showed** (UK Home Office "Recovery and Acquisition of Video Evidence" v3.0, the public standard):
  - "Any discrepancy between the system time and real time should be recorded in the audit trail" (3.3(a)).
  - Record the period covered and draw a plan of the camera views.
  - The master is "the definitive copy of the data", kept in native format. Working copies must be uniquely
    identifiable, and a non-native copy is marked "Converted Format".
  - Hashes are compared before and after each transfer.
  - "Continuity of evidence [must be] maintained and documented."
  - The NZ Crown Law CCTV guideline adds that the chain-of-custody record starts when the footage is collected.
- **What we changed:**
  - Operator form renamed **"CCTV retrieval: import a recorder clip"**, with two new fields:
    - a *case or claim reference*, stored as the media authorization's purpose;
    - a *clock check at retrieval* (recorder minus reference, in seconds). When given, it is recorded as the camera's
      clock sync (offset −d, ±1 s, method "clock check at retrieval…") before the clip is placed on the timeline.
      Left empty, the clip stays "clock unverified".
  - Source panel: chip reads **"master (original)"**, and during play **"playing · working copy"**. The rows are
    *Master*, *Master SHA-256*, *Working copy … converted format (H.264)* and *Clock check*. The camera wall caption
    uses the same terms.
  - Report: **"CCTV reviewed"** table, one row per camera in scope and clip covering the case window. It shows the
    period, master SHA-256, working copy with its method, clock check, and "not analysed" when nothing was observed
    (so footage that was never analysed is still listed, not hidden). Plus **"Continuity of evidence (audit trail)"**:
    who imported each item, when, purpose, rights, retain-until, and the scan-log batches.
- **Sources:**
  - https://www.gov.uk/government/publications/recovery-and-acquisition-of-video-evidence/recovery-and-aquisition-of-video-evidence-v30
    (sections 2.3, 3.2, 3.3(a)(b)(e)(p), 3.5)
  - https://www.crownlaw.govt.nz/assets/Uploads/Prosecution-Guidelines/digital-cctv-evidence-guidelines.doc

### G3 · Scan history in the workspace, like an ops scan-history screen
- **Research showed:**
  - Customers see coarse statuses such as "Arrived at Sorting Facility", and couriers update tracking only after major
    movements (Ninja Van MY's 17 statuses).
  - Ops investigators work from the detailed per-scan history and look for gaps (G1 sources).
- **What we changed:**
  - The Case panel has a **Scan history** list: every scan of the waybill, time-ordered.
  - "No scan for N min" appears between scans 1 min or more apart.
  - Each row is flagged "device time" or "uploaded late" where it applies, and opens its source on click.
  - It is captioned "Where it was scanned, not where it went."
- **Sources:**
  - https://blog.ninjavan.co/en-my/?p=10819 (17 parcel tracking statuses explained, Ninja Van MY, 5 May 2025)

### G4 · Malaysian logistics terms
- **Research showed:**
  - In Malaysia the consignment note, airway bill and shipping label are the same document, named differently by
    courier (DHL MY).
  - Bags are dispatch receptacles that are closed and listed (UPU letter bill CN 31: "generated … when the dispatch is
    closed").
- **What we changed:**
  - "Start a case" field is now **"Waybill / tracking no. (consignment note, AWB)"**, captioned "the number on the
    consignment note the customer quotes".
  - The Cases intro now says a case "traces one consignment reported not received".
  - Bag scans read **"bagging: new bag opened / bagging: bag closed"** (card "bagging scan (handheld)").
  - Report uses manifest / linehaul / POD (G1).
- **Sources:**
  - https://www.dhl.com/discover/en-my/logistics-advice/essential-guides/airway-bill-introduction
  - https://www.upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/physicalServices/FcdCN31En.pdf

### Decided not to change (sources disagree or are not authoritative)
- **Claim deadlines and compensation caps are not shown.** The figures conflict: 48 h for damage, 5 days (J&T, news
  report), 14 business days (Ninja Van, secondary source), and Pos Laju RM300 (unverified guide). MCMC's newer Code of
  Practice for Postal Services (launched Nov 2025) is guidance and I couldn't read its text. A wrong deadline on screen
  would be worse than none.
  - https://www.thestar.com.my/news/nation/2025/11/02/code-of-practice-for-couriers-to-enhance-service
  - https://says.com/my/news/mcmc-issues-warning-to-j-t-express-over-video-showing-staff-mishandling-customers-parcels
- **Customer-status mapping not added** (for example tunnel read → "Arrived at Sorting Facility"). The courier's
  mapping is internal. Guessing it would be fabrication.

## 2. Check these
- `frontend/review_pack/desktop/26_report_document_full.png` (the whole report document with the new sections), `08_case_overview.png` (scan history), `04_source_context_frame.png` and
  `22_source_context_playing.png` (master / working copy), `13_report_draft.png` and `14_report_approved.png` (new
  report sections), `15_operator.png` (CCTV retrieval form). Same names under `mobile/`.
- `backend/src/spoor/reports.py` (`_scan_history`, `_footage_reviewed`, `_continuity`, `_records_not_held`),
  `frontend/src/components/workspace/CaseOverview.tsx` (`ScanHistory`), `frontend/src/app/operator/page.tsx`
  (`ImportClip`).
- Tests: frontend typecheck ✓, lint ✓, unit 20/20 ✓, e2e 17/17 ✓ (smoke + axe AA), review pack 20/20 + new `26_report_document_full.png`; backend pytest 217 ✓ (new report assertions in `test_parcel_scan_routes`).

## 3. Known issues
- **RFID dock-portal reads (`rfid_read`, S4) are skipped by the seed today** and only counted in `seed_report.json`.
  So the "linehaul loading" row can't be "held" for S4 yet. Proposed for F1: import them as container scans from an
  `rfid_portal` device at the dock door. They must not be marked "loaded": a portal read can be a cross-read, which is
  the whole point of S4. I'd like the reviewer's view on this.
- The clock-check field records the operator's reading at ±1 s. It is an input, not a fit. Anchor fitting still needs
  observed events (SAM).

## 4. Questions
1. RFID mapping for F1 (above): OK to add a dedicated "portal read" scan kind, rather than reuse `container_loaded`?
