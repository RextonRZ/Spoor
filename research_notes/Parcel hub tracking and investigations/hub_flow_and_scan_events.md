# Parcel Hub Process Flow and Scan Events (for designing a model that fuses scan logs with CCTV)

Research date: 2026-10-28. Source quality is mixed. Primary sources: UPU EMSEVT standard material, a Pitney Bowes developer table of USPS event codes, AfterShip's sub-status taxonomy, and DHL developer support pages. Physical hub-flow detail comes mostly from vendor marketing and patents. Each item is flagged where relevant.

---

## 1. Stages of the parcel journey and what physically happens inside a hub

### Takeaway
A hub visit follows a fairly standard physical chain: trailer unload, singulation and orientation, induction onto a sorter, an automated scan/dimension/weigh step in a tunnel, discharge to a chute, consolidation into a bag, cage or pallet (container close), and outbound load. Exceptions (no-read, oversized, damaged) branch off to manual handling. The UPU EMSEVT standard models the journey at the facility level (posting, office of exchange in/out, sorting centre in/out, delivery office, out for delivery, delivered). It does not model it at the within-hub station level.

### Cited Findings
- **Unloading:** inbound trailers are emptied by hand or by robots. Vision-guided arms and mobile unloading robots pull loose-loaded parcels onto conveyors, or whole cages are moved to sortation. — [BEUMER Group, "7 workflows where robotics can optimise parcel hub operations" (vendor)](https://www.beumergroup.com/knowledge/cep/7-workflows-where-robotics-can-optimise-parcel-hub-operations/). Trailer unloading is described as one of the most physically demanding and time-consuming hub tasks (same search synthesis, vendor sources).
- **Singulation and orientation:** AI vision detects overlapping parcels, and robot arms separate them and turn them into the right orientation so they form one continuous stream before sortation. — [BEUMER (vendor)](https://www.beumergroup.com/knowledge/cep/7-workflows-where-robotics-can-optimise-parcel-hub-operations/)
- **Induction:** parcels are metered onto cross-belt or tilt-tray sorters, either manually or by robotic pick-and-place. Manual induction stations are cited at a practical ceiling of about 1,500–2,000 items/hour. — [Motion Tech, "Sorter Induction" (vendor)](https://www.motiontech.co.uk/sorter-induction); [BEUMER (vendor)](https://www.beumergroup.com/knowledge/cep/7-workflows-where-robotics-can-optimise-parcel-hub-operations/). Pitney Bowes describes robotic arms inducting parcels onto a belt that feeds scan tunnels ahead of the primary sorter. — [MMH, Pitney Bowes sortation and robotics layout](https://www.mmh.com/article/sortation_and_robotics_layout_at_pitney_bowes/Automation). A USPTO patent describes induction zones sized so that each item can be scanned without interference from neighbouring items. — [USPTO 11911803](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11911803)
- **Scan/identify:** barcode readers read the label in any orientation and dimensioning cameras capture L×W×H. The sort controller uses this data to assign a destination lane, and a warehouse control system tracks each item from scan to discharge. — vendor sources summarised from [Dematic Sortation Solutions brochure](https://www.dematic.com/content/dam/dematic/downloads/brochures/NA_BR-1070_Dematic-Sortation-Solutions.pdf) and [Flostor](https://www.flostor.com/solutions/parcel-shipping) (vendor marketing)
- **Sortation:** on a cross-belt sorter, each carrier cell drives its own belt to discharge the parcel into the correct chute. Linear sorters use sliding shoes or diverters. — [Fives parcel distribution (vendor)](https://www.fivesgroup.com/smart-automation-solutions/your-markets-our-solutions/parcel-postal/parcel-distribution); patents in the same search ([USPTO 6478138, double-width crossbelt](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6478138))
- **Consolidation:** a sorter outlet "can be a conveyor, chute, bag, roller cage, or any other container that receives all the parcels addressed to the same destination". — patent language, [USPTO 11958080](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11958080)
- **Outbound:** robots palletise or cage mixed parcels and plan stacking to fill trailers. Route-sequencing robots arrange parcels by delivery route, stop order or wave before loading. AMRs/AGVs move parcels, pallets and roll cages between zones and buffers. — [BEUMER (vendor)](https://www.beumergroup.com/knowledge/cep/7-workflows-where-robotics-can-optimise-parcel-hub-operations/)
- **Ship sorters as the last scan point:** Cognex says the ship sorter is "often the last scanning point prior to going onto a truck. No reads at this point means re-circulation and manual handling." — [Cognex Ship Sorter Scanning (vendor)](https://www.cognex.com/industries/logistics/sortation/ship-sorter-scanning)
- **UPU network model (EMSEVT V3 event structure, 2017 UPU training deck):**
  - Origin operator: Post office (EMA) → Office of Exchange (EMB arrival, EXD held, EMC departure, with export customs/security EXA/EXB/EXC).
  - Transit operator: EMJ/EMK.
  - Destination operator: Office of Exchange (EMD, EDA, import customs EDB/EME/EDC, EMF) → Sorting centre (EDD into, EDE out of) → Delivery depot (EMG, EDF, EDG) → Delivery (EMH, EMI), plus collection pick-up (EDH).
  - Despatch-level messages PREDES/RESDES carry the container hierarchy Despatch (ID, closed date-time, planned arrival) → Receptacle (ID, scanned date-time, status) → Item (ID).
  - Source: [UPU/EMS, "EMSEVT V3 part 2" (2017)](https://www.ems.post/sites/default/files/content-block-files/EMSEVT%20V3%20part%202.pdf)

### Inferences
- For a data model, the physical chain implies an ordered set of **station types** within a hub: `DOCK_IN (door) → UNLOAD → SINGULATE → INDUCT → SCAN_TUNNEL → SORTER_CARRIER (in motion) → CHUTE/DESTINATION → CONTAINER (bag/cage/pallet/ULD) → STAGING → DOCK_OUT (door) → TRAILER`. Exception branches go to `NO_READ_LANE`, `MANUAL_ENCODE/RELABEL`, `HOSPITAL/DAMAGE`, `OVERSIZE/NON-CONVEYABLE` and `RECIRCULATION`. Each station is a natural anchor for one or more CCTV camera fields of view.
- The UPU container hierarchy (despatch → receptacle → item) shows that after consolidation the parcel's location is **inherited from its container**. Once bagged, later scans are often of the bag or cage, not the parcel. The model needs an item↔container association table with time validity (`bagged_at`, `unbagged_at`).
- First mile (pickup/drop-off) and last mile (out for delivery → delivered/attempted) happen outside hubs. Returns run the same flow in reverse with distinct status codes (e.g., USPS RTS family, AfterShip Exception_010/011).

### Gaps
- I found no authoritative, vendor-neutral, step-by-step standard for intra-hub process stages. The sequence above is synthesised from vendor material and patents.
- I found no specific description of Malaysian hub layouts (Pos Malaysia's Integrated Parcel Centre, J&T or Ninja Van Malaysian hubs).
- Linehaul and ULD (air cargo container) specifics were not researched in depth.

---

## 2. Scan points: which exist, and which are automated vs handheld

### Takeaway
The automated scan points are the induction/sorter scan tunnel (often with dimensioning, weighing and, in vendor products, video/image capture on no-reads) and sometimes the ship sorter at the outbound end. Handheld or manual scans cover unload/arrival, manual-encode and no-read rework, container close (bagging), load-to-trailer, and every first- and last-mile event (pickup, out for delivery, delivery/POD, attempt).

### Cited Findings
- Fixed scan tunnels read barcodes on parcels moving on the conveyor. Cognex claims multi-sided tunnels read codes at angles up to 85° and achieve "up to 99.9%" read rates. — [Cognex (vendor marketing claim)](https://www.cognex.com/industries/logistics/sortation/ship-sorter-scanning)
- A Zebra tunnel product "captures and stores video whenever a non-read event occurs". This is a vendor claim, but it is directly relevant: some tunnels already create image/video evidence tied to no-read events. — [MH&L, "Scan Tunnel" (product announcement)](https://mhlnews.com/new-products/product/55277733/scan-tunnel)
- Dimensioning cameras in the scan step capture L×W×H. — [Dematic brochure (vendor)](https://www.dematic.com/content/dam/dematic/downloads/brochures/NA_BR-1070_Dematic-Sortation-Solutions.pdf)
- USPS event codes include container-level and handling scans that show the range of scan points:
  - C1 "Container close", P1 "Placard assign", 41 "Received at opening unit", 35 "Vault turnover", 36 "Transfer to employee"
  - OA "Accepted at USPS origin facility", 10 "Processed through USPS facility", NT/TL "In transit to next facility"
  - EA/ED "Enroute arrival/departure", DE/EF/L1 "Departed USPS facility"
  - 59/OF/DG "Out for delivery", 01/DL "Delivered (with signature)"
  - Source: [Pitney Bowes Shipping API, USPS tracking event codes (third-party integration doc)](https://docs.shippingapi.pitneybowes.com/reference/tracking-codes.html)
- In the UPU model, receptacle (bag) scans carry their own "scanned date-time" and status in RESDES. — [UPU/EMS EMSEVT V3 deck](https://www.ems.post/sites/default/files/content-block-files/EMSEVT%20V3%20part%202.pdf)

### Inferences
- Map each scan point to a mode:
  - **Automated/fixed:** induction/tunnel scan; sorter discharge confirmation (sort controller event, not always a customer-visible scan); ship-sorter scan; DWS (dimension-weight-scan) stations.
  - **Handheld/manual:** door/unload arrival scan; manual encode at no-read; damage/hospital scan; bag/cage close; load-to-trailer/door scan; driver pickup and delivery scans (mobile device with GPS and photo POD).
- Customer-facing tracking feeds usually collapse many internal scans into a few events (USPS "Processed through facility", AfterShip "Arrival scan"/"Departure scan"). The internal WCS/sorter logs are far denser. Spoor should ingest internal scan logs, not public tracking, to localise a parcel within a hub.

### Gaps
- I found no carrier-published list of the internal (non-customer-facing) scan types used by UPS, FedEx, J&T or Ninja Van.
- I found no independent, non-vendor benchmark of tunnel read rates. An older [Inbound Logistics article](https://www.inboundlogistics.com/articles/tunnel-scanning-in-consolidation-warehouses/) gives the arithmetic that even a 99% read rate on 126,760 packages/day leaves about 1,268 no-reads/day. That article is dated and illustrative.

---

## 3. Status and event codes used by carriers and aggregators

### Takeaway
The best-documented public code sets are the UPU EMSEVT events (three-letter codes used between postal operators), USPS's two-character scan codes, and the normalised taxonomies of aggregators such as AfterShip (tag + subtag), Pitney Bowes (l1Code) and DHL Unified (five status codes). Carrier-specific SE Asian codes (J&T, Ninja Van, Pos Malaysia) are only exposed as free-text status strings in public sources.

### Cited Findings

**UPU EMSEVT V3 (M40 standard)**
- Source: [UPU/EMS EMSEVT V3 deck, 2017](https://www.ems.post/sites/default/files/content-block-files/EMSEVT%20V3%20part%202.pdf)
- Export events: EMA Posting/collection; EMB Arrival at outward office of exchange; EXA Item presented to export customs/security; EXB Item held by export customs/security; EXC Item returned from export customs/security; EXD Item held at outward office of exchange; EMC Departure from outward office of exchange; EXX Export cancellation; EMJ Arrival at transit office of exchange; EMK Departure from transit office of exchange.
- Import events: EMD Arrival at inward office of exchange; EDA Held at inward office of exchange; EDB Item presented to import customs; EME Held by import customs; EDC Item returned from customs (import); EMF Departure from inward office of exchange; EDD Item into sorting centre; EDE Item out of sorting centre; EMG Arrival at delivery office; EDF Item held at delivery depot; EDG Item out for physical delivery; EDH Item arrival at collection point for pick-up; EDX Import terminated; EMH Unsuccessful (physical) delivery; EMI Final delivery.
- Reason codes (UPU code list 112) and action codes (CL 113) accompany events such as EXD, EXX, EDA, EDF, EDX and EMH. Reference list 112b gives the allowed event/reason combinations. — [UPU EMSEVT compliance explanatory notes v2.0, 2025-03-01](https://www.upu.int/getmedia/e8c5a980-cd96-4b0b-8ba5-ddd3adb8a02c/complianceWithUpuStandardsExplanatoryNotesEMSEVTEn.pdf)
- EMA and EMI typically occur only once per item, while events such as EDD, EDE and EMH may legitimately repeat. — [UPU explanatory notes on EMSEVT repeated events](https://upu.int/getmedia/405ea48f-01e3-4a6c-86f2-611142cf619c/complianceWithUpuStandardsExplanatoryNotesEMSEVTRepeatedEventsEn.pdf) (via search snippet; not fully read)

**USPS** (via the Pitney Bowes mapping; the source cites USPS Publication 97 for the full list)
- Source: [Pitney Bowes USPS tracking codes](https://docs.shippingapi.pitneybowes.com/reference/tracking-codes.html)
- Delivery and attempts: 01 Delivered; 02 Notice left; 59/OF/DG Out for delivery; 30/51 Delivery attempted – no access; 53 Receptacle blocked; 55 No secure location; 56 No authorized recipient.
- Acceptance and facility movement: 03 USPS in possession; 07 Arrived at post office; 08/15/34/A1/RB/RC Arrived at USPS facility; 10 Processed at USPS facility; DE/EF/L1 Departed USPS facility; NT/TL In transit to next facility.
- Container and custody: C1 Container close; P1 Placard assign; 35 Vault turnover; 36 Transfer to employee.
- Exceptions: 12 Visible damage; DN Delivered damaged; **MS Missort**; MC Miscode; 46 Duplicate label ID; LT Missed delivery cycle; LX/OX Processing exception; TX regional transportation delay; WX weather delay; BX Bumped delay; OH On hold.
- Disposal and recovery: 32 Disposed by post office; 33 Sent to mail recovery center.
- **Missing-mail lifecycle codes:** VM Missing mail search request initiated; VN reminder; VO closed; VX Package research case closed.
- Pre-shipment: GX Shipping label created / awaiting item.
- Pitney Bowes normalises these to l1Code values: DLD delivered, DAT delivery attempt, OFD out for delivery, TRD in transit, UDL undeliverable/exception, RTS return to sender, DYU delayed, AWP awaiting pickup, PSR pre-shipment, INF info, SPH shipped.

**AfterShip (normalised tag/subtag taxonomy)**
- Source: [AfterShip, "Learn about delivery sub-status"](https://support.aftership.com/en/articles/15441382-learn-about-delivery-sub-status); versioned enum pages exist at [AfterShip docs 2025-07](https://www.aftership.com/docs/tracking/2025-07/enum/delivery-sub-statuses) (returned 403 to fetch)
- Top-level tags: Pending, InfoReceived, InTransit, OutForDelivery, AvailableForPickup, AttemptFail, Delivered, Exception, Expired.
- In-transit subtags: InTransit_002 "Acceptance scan", InTransit_003 "Arrival scan" (reached a hub/sorting centre), InTransit_007 "Departure scan", InTransit_008 "Problem resolved", InTransit_013 "Dropped off for carrier pickup".
- Exception subtags: Exception_012 "Shipment damaged", Exception_013 "Shipment lost", Exception_016 "Delayed (Processing issue)", Exception_021 "Shipment disposed".
- Pending/Expired: Pending_003 "Label created, no updates yet", Pending_005 "No recent updates" (120 days), Expired_001 (no tracking info in the last 30 days).

**DHL Shipment Tracking – Unified API**
- statusCode values are pre-transit, transit, delivered, failure and unknown. More granular codes (out for delivery, return to origin, ready for pick-up) were described as planned. — [DHL developer support](https://support-developer.dhl.com/support/solutions/articles/47001197243-what-are-the-different-status-codes-available-in-the-dhl-shipment-tracking-unified-api-)
- Status descriptions are division-specific free text, e.g. "Received & processed at Deutsche Post Mail Terminal", "Departed Deutsche Post Mail Terminal", "Held at customs". — [DHL developer support](https://support-developer.dhl.com/support/solutions/articles/47001242928-shipment-tracking-unified-list-of-possible-status-descriptions)
- Events can arrive out of order: for Deutsche Post (parcel-de), a "pre-transit" event can arrive after transit or delivered events. — [DHL developer support](https://support-developer.dhl.com/support/solutions/articles/47001271948-i-m-receiving-a-delayed-pre-transit-status-event-once-the-shipment-is-already-in-transit-or-deli)

**FedEx Track API**
- Detailed scans come back in `scanEvents`, with an `eventType` code. The official catalog page publicly shows only the 2021 additions AE (arriving early) and AO (arriving on time). — [FedEx Developer Track API](https://developer.fedex.com/api/en-am/catalog/track.html)
- An unofficial guide notes that `includeDetailedScans=true` is required to get the scanEvents. — [browse.sh](https://browse.sh/skills/fedex.com/track-package-7fxxv5)

**SE Asia**
- Ninja Van customer-facing statuses include "Arrived at Sorting Hub" (arrived and processed at a sorting hub) and "On Vehicle for Delivery". Wording varies by country (Indonesia uses Ninja Xpress wording). — aggregator explainers via [Ninja Van tracking page](https://www.ninjavan.co/en-ph/tracking) and [ParcelPanel](https://www.parcelpanel.com/couriers/ninjavan-my/) (secondary)
- J&T statuses as reported by aggregators: "Processed at J&T Express" (scanned into a depot), "At J&T Express sorting center", plus Outbound/Inbound/On Hold. — [TrackingMore (aggregator)](https://m.trackingmore.com/jet-tracking.html); [Ship24 (aggregator)](https://ship24.com/couriers/jt-express-tracking)

### Inferences
- Spoor should adopt a **two-level code scheme**: keep the raw carrier code and text (`raw_code`, `raw_description`) and map them to a normalised enum. Suggested values: `PRE_TRANSIT`, `PICKED_UP`, `ARRIVED_FACILITY`, `PROCESSED/SORTED`, `CONTAINERISED`, `DEPARTED_FACILITY`, `OUT_FOR_DELIVERY`, `DELIVERED`, `ATTEMPT_FAILED`, `EXCEPTION_{DAMAGE|MISSORT|NO_READ|HOLD|LOST|DISPOSED}`, `RETURN`. This mirrors what Pitney Bowes (l1Code) and AfterShip (tag/subtag) do.
- EMSEVT's EDD/EDE ("into/out of sorting centre") pair is the cleanest standard expression of the "scanned in but never out" pattern. For each facility visit, Spoor can pair an arrival-type event with a departure-type event.
- Unconfirmed, from prior knowledge (verify before use): the UPS Track API returns an activity `status.type` of I (in transit), D (delivered), X (exception), P (pickup) or M (manifest/label created). Treat this as uncited.

### Gaps
- I could not access a full public FedEx eventType list (e.g., PU, AR, DP, OD, DL, DE, SE) or the UPS activity code list from official docs in this session.
- I found no official Ninja Van webhook event list (api-docs.ninjavan.co returned 404), no J&T Malaysia API docs, and no Pos Malaysia event-code documentation.
- No Royal Mail, Australia Post or 17TRACK code lists were retrieved.

---

## 4. Data fields per scan event

### Takeaway
A scan event at minimum carries: item ID, event code, event date-time, and an event location/office code. Optional fields include the reason code, action code, weight, dimensions, container/receptacle ID, signatory (at delivery) and the next/destination office. Device ID, operator ID, chute/door and image references live in internal WMS/sorter logs, not in public APIs.

### Cited Findings
- EMSEVT field example for EDB (Item presented to import customs): `item-identification` (M), `destination-country` (M), `event-date-time` (M), `receiving-OE` (M, CL 108), `import-customs-office-ID` (MC), `import-customs-facility-type` (M, local/remote, CL 200), `item-origin-country` (C), `item-origin-operator` (C), `item-ID-type` (C). Obligation levels are M = mandatory, MC = mandatory under conditions, R = recommended, C = conditional/bilateral. — [UPU/EMS EMSEVT V3 deck](https://www.ems.post/sites/default/files/content-block-files/EMSEVT%20V3%20part%202.pdf)
- Other EMSEVT data elements referenced by the compliance rules — [UPU EMSEVT compliance notes v2.0, 2025](https://www.upu.int/getmedia/e8c5a980-cd96-4b0b-8ba5-ddd3adb8a02c/complianceWithUpuStandardsExplanatoryNotesEMSEVTEn.pdf):
  - Item and location: event office as an IMPC code from CL 108 (for EMB, EXD, EMC, EMJ, EMK, EMD, EDA, EDB, EME, EDC, EMG); `outward-OE`; `destination-country`.
  - Item attributes: `item-subclass` (CL 117); `item-handling-class`; `item-weight` (format ≤9999.999, gross weight preferred); volume; `item-delivery-location-type` (CL 199).
  - Codes and despatch: reason code (CL 112); action code (CL 113); `despatch-number`.
  - Delivery: `signatory-name` (EMH/EMI).
  - Origin and parties: sender/delivery postcode; sender/addressee email and phone; `orig-operator`; `orig-country`; `office-of-origin-ID`; `place-of-origin`.
- Item IDs follow UPU S10: 13 characters (2 letters service indicator + 9 digits including a check digit + 2-letter country). The compliance checks validate the check digit, reject lower-case characters, and reject an invalid service indicator (CL 124). — [UPU compliance notes](https://www.upu.int/getmedia/e8c5a980-cd96-4b0b-8ba5-ddd3adb8a02c/complianceWithUpuStandardsExplanatoryNotesEMSEVTEn.pdf)
- Despatch/receptacle level (PREDES/RESDES) — [UPU/EMS deck](https://www.ems.post/sites/default/files/content-block-files/EMSEVT%20V3%20part%202.pdf):
  - Despatch: ID, closed date-time, planned arrival, actual arrival.
  - Receptacle: ID, scanned date-time, status.
  - Item: ID.
- Pitney Bowes Tracking API fields: `scanType` (USPS code), `l1Description`, `l1Code`. Webhook fields: `eventCode`, `eventDescription`, `StandardizedEventCode`, `StandardizedEventDescription`. — [Pitney Bowes](https://docs.shippingapi.pitneybowes.com/reference/tracking-codes.html)
- DHL Unified events include a `location` with an address locality, a status code, and a free-text `statusMessage`/description. — [DHL developer support](https://support-developer.dhl.com/support/solutions/articles/47001242928-shipment-tracking-unified-list-of-possible-status-descriptions)
- Sorter scan stations capture dimensions (L×W×H), and the controller assigns a destination lane. — [Dematic (vendor)](https://www.dematic.com/content/dam/dematic/downloads/brochures/NA_BR-1070_Dematic-Sortation-Solutions.pdf)
- Some tunnels store video for no-read events. — [MH&L/Zebra (vendor)](https://mhlnews.com/new-products/product/55277733/scan-tunnel)

### Inferences
Suggested Spoor `scan_event` schema, synthesised from the above. Internal fields such as device/operator are standard WMS practice but not documented in the public sources found.

| Group | Fields |
|---|---|
| Identity | `event_id`, `tracking_id` (+ `id_scheme`: S10 / carrier waybill / internal), `raw_code`, `raw_description`, `norm_status`, `reason_code`, `action_code` |
| Time | `event_ts_local` + `tz_offset` (or UTC + facility tz); separate `event_ts` from `received_ts` because events can arrive late or out of order (DHL example) |
| Where | `facility_code` (IMPC-style), `zone`, `station_type` (unload/induct/tunnel/chute/container/door/vehicle), `station_id` (chute/lane/door number), `camera_ids_covering` (link to CCTV) |
| Who/what | `device_id` (fixed scanner or handheld), `scan_mode` (fixed/handheld/mobile), `operator_id`, `vehicle_id`/`route_id` |
| Physical | `weight_g`, `dims_mm`, `image_ref` |
| Container | `container_id`, `container_type` (bag/cage/pallet/ULD/trailer), `parent_container_id`, `container_event` (open/close/placard) |
| Routing | `next_facility`/`destination_facility`, `sort_destination` (the assigned chute) |
| Delivery | `gps`, `pod_photo_ref`, `signatory_name` |

### Gaps
- I found no public source documenting device ID, operator ID, chute or door fields for any specific carrier. These are inferred to exist in internal systems.
- I could not confirm how carriers encode timezones in public APIs. FedEx and UPS details were not retrieved.

---

## 5. Scan frequency inside a hub and typical gaps / blind periods

### Takeaway
Customer-visible tracking often shows only an arrival and a departure (or a single "processed") scan per facility. Inside the hub, the period between the induction/tunnel scan and the container close or load scan is often unscanned, as are trailer transit, staging/dwell areas and recirculation. I found no reliable published figures for typical intra-hub scan intervals.

### Cited Findings
- A parcel can pass through a facility with only entry and exit scans, so gaps between scans do not by themselves mean loss. — [Parcel Monitor lost-package claims guide (secondary)](https://www.parcelmonitor.com/blog/lost-package-claims-guide) / similar guides in the same search
- In practice, the "real loss" test used by consumer guides is tracking static for more than about 48–72 hours past the expected delivery date with no hub scan update. — [Parcel Monitor (secondary)](https://www.parcelmonitor.com/blog/lost-package-claims-guide); [Pango (secondary)](https://pango.ai/resources/parcel-lost-in-transit)
- AfterShip flags Pending_005 at no updates for 120 days and Expired_001 at no tracking info for 30 days. These are aggregator staleness thresholds, not hub norms. — [AfterShip](https://support.aftership.com/en/articles/15441382-learn-about-delivery-sub-status)
- Manual induction of about 1,500–2,000 items/hour per station implies that a parcel's induction-to-discharge time on the sorter itself is seconds to minutes. — [Motion Tech (vendor)](https://www.motiontech.co.uk/sorter-induction) (inference on timing)

### Inferences (not directly sourced; for model design)
Likely blind periods inside a hub:
1. **Door to induction:** trailer unload, pile or cage staging, and the singulation queue. There is often no item-level scan until the tunnel if no unload scan is done.
2. **Recirculation loops:** the parcel is physically on the sorter but has no successful read.
3. **No-read/exception lanes and manual encode benches**, until re-scan.
4. **Chute to container close:** parcels sit in the chute until a bag or cage is closed and scanned. After that the location is inherited from the container.
5. **Staging/dock dwell to trailer load scan.**
6. **Linehaul:** trailer/ULD in motion. Only trailer- or despatch-level events exist (EMSEVT despatch closed/arrival; USPS EA/ED enroute).

These are exactly the windows where CCTV can supply the last-seen evidence. Expect gaps of seconds to minutes within the sort itself, and up to many hours for dwell and linehaul. The hour-level figure is inferred and unsourced.

### Gaps
- I found no published empirical distribution of inter-scan intervals within hubs (minutes or hours) for any carrier, and no data on scan density per hub visit for SE Asian carriers.

---

## 6. Exception flows: no-read, rework/relabel, damage, hospital, overflow, recirculation

### Takeaway
Parcels the tunnel cannot read are recirculated or diverted to a no-read lane for manual encode/relabel and reinduction. Damaged, oversized, leaking or unlabeled parcels are pulled from the main flow to manual "hospital" handling. Each of these flows creates a gap in, or a reset of, the scan chain.

### Cited Findings
- An item that fails to scan is diverted to a no-read lane or recirculated, using up another sorter carrier. — vendor synthesis via [Dematic](https://www.dematic.com/content/dam/dematic/downloads/brochures/NA_BR-1070_Dematic-Sortation-Solutions.pdf) / [Flostor](https://www.flostor.com/solutions/parcel-shipping) (vendor)
- At a ship sorter, "No reads at this point means re-circulation and manual handling." — [Cognex (vendor)](https://www.cognex.com/industries/logistics/sortation/ship-sorter-scanning)
- Recirculation SOP: the operator reviews cartons returned from the recirculation loop and decides whether to reintroduce or divert to exception handling. The operator re-scans and reinduces only when the induction point is clear and singulation can be maintained. — [MangoApps sortation induction SOP template (generic template, not carrier-specific)](https://www.mangoapps.com/templates/sop/sortation-induction-standard-operating-procedure)
- OCR fallback: no-reads can be recovered by reading the address block, postal code or routing text when the barcode is folded, torn or missing, instead of sending the parcel to manual encode. — [Roboflow (vendor)](https://roboflow.com/ai/parcel-sorting-computer-vision)
- Robotic exception handling: vision and AI identify oversized, damaged, leaking or unreadable-label parcels and remove them from the main flow for manual handling. — [BEUMER (vendor)](https://www.beumergroup.com/knowledge/cep/7-workflows-where-robotics-can-optimise-parcel-hub-operations/)
- Carrier exception codes that reflect these flows (USPS): 12 Visible damage, MS Missort, MC Miscode, 46 Duplicate label ID, LX/OX Processing exception, 32 Disposed, 33 Sent to mail recovery center. — [Pitney Bowes](https://docs.shippingapi.pitneybowes.com/reference/tracking-codes.html)
- The UPU attaches reason codes (CL 112) to hold/termination events (EXD, EXX, EDA, EDF, EDX, EMH). — [UPU/EMS deck](https://www.ems.post/sites/default/files/content-block-files/EMSEVT%20V3%20part%202.pdf)

### Inferences
- Model exception handling as **branch states** with entry and exit events: `NO_READ_DIVERT → MANUAL_ENCODE/RELABEL → REINDUCT`, `DAMAGE_DETECTED → HOSPITAL (repack) → REINDUCT or HOLD`, `MISSORT_DETECTED → REROUTE`.
- Relabelling can change the barcode ID. Spoor needs an **ID-alias table** (old label ↔ new label) or the parcel will appear to vanish.
- Tunnels that save no-read images or video (vendor claim) are a natural bridge between scan data and CCTV.

### Gaps
- I found no carrier-published hospital-line or overflow-chute procedure. The term "hospital line" itself was not confirmed by a source in this session.
- I found no published no-read rates for SE Asian e-commerce hubs.

---

## 7. Missing-parcel investigations and "last known scan"

### Takeaway
Investigations are triggered by a customer or merchant claim, typically once a parcel is static for about 48–72 hours or more past its expected date, or by a disputed delivery scan. The carrier starts from the last scan's location and time, physically searches that facility, checks transport logs and the driver/GPS, and only "if needed" reviews CCTV. USPS exposes an explicit missing-mail case lifecycle in its event codes.

### Cited Findings
- USPS tracking includes VM "Missing mail search request initiated", VN "reminder", VO "closed", and VX "Package research case closed". The investigation lifecycle is therefore itself part of the event stream. — [Pitney Bowes USPS codes](https://docs.shippingapi.pitneybowes.com/reference/tracking-codes.html)
- Typical trace steps include:
  - checking the last scanned location and time, and the last known GPS coordinate of the scan;
  - searching the physical hub where the parcel was last seen;
  - interviewing the driver if a delivery is disputed;
  - checking sorting-facility scans and transport logs, confirming delivery attempts, and searching nearby branch warehouses;
  - CCTV review is mentioned only as done "if needed".
  - Sources: [Parcel Monitor (secondary)](https://www.parcelmonitor.com/blog/lost-package-claims-guide); [PACKAGE TODAY (secondary)](https://pkg2day.com/how-courier-services-handle-lost-parcels/); [iCarry India (secondary)](https://www.icarry.in/pages/blog/courier-shipment-missing-india.html)
- FedEx domestic traces are cited at about 5–10 business days, and another source says 7–10 business days before a claim can be filed. These are secondary sources and conflict slightly. — [ShipAid (secondary)](https://www.shipaid.com/blogs/ecommerce-shipping/managing-a-fedex-investigation-for-a-lost-package); [Pango (secondary)](https://pango.ai/resources/parcel-lost-in-transit)
- Carriers rarely post an explicit "lost" status. "Lost" usually enters through the claims process. AfterShip does include Exception_013 "Shipment lost". — [Parcel Monitor (secondary)](https://www.parcelmonitor.com/blog/lost-package-claims-guide); [AfterShip](https://support.aftership.com/en/articles/15441382-learn-about-delivery-sub-status)
- Sellers often have more leverage than recipients to open a trace. — [Parcel Monitor (secondary)](https://www.parcelmonitor.com/blog/lost-package-claims-guide)

### Inferences
Investigation triggers Spoor can detect automatically:
- (a) **Arrived but never departed:** an arrival/induction event at facility F with no subsequent departure/container/load event within an SLA window. This is the EMSEVT EDD-without-EDE or USPS 08/10-without-DE/EF pattern.
- (b) **Containerised but container arrived without the item:** item scanned into bag B; bag B scanned at the next facility; item not unbagged there.
- (c) **Out for delivery but no delivered/attempt scan by end of route.**
- (d) **Delivered disputed:** compare the POD GPS and photo with the address.
- (e) **Missort:** a scan at the wrong facility, or a sort destination ≠ assigned chute.

The "last known location" should be computed as the **latest trustworthy observation across both scans and CCTV detections**, with container inheritance applied. If the last item scan is "into bag B", the last-known location is the last scan of bag B. Each observation should carry a confidence: a fixed-scanner read is high confidence, a CCTV re-identification is probabilistic.

### Gaps
- I found no primary carrier SOP for hub-level missing-parcel investigation, including how CCTV is retrieved or retained. All sources here are secondary consumer guides.
- I found nothing on Malaysian practice: Pos Malaysia, J&T or Ninja Van claim windows, or the MCMC courier complaints process.
