# Parcel identifiers, labels and supply-chain event data standards (as of Oct 2026)

Scope: how parcels and the containers that hold them are identified and labelled, and how scan and visibility events are modelled in the standards, to inform the event model of a system that fuses barcode scans with CCTV observations.

Source note: the GS1 EPCIS 2.0, CBV 2.0, GS1 Logistic Label Guideline 1.3, UPU S10-12 and UPU S9 texts were downloaded as PDFs and read directly with pdftotext, so field names and quotes below come from the primary documents. Material on scanner read rates and carrier APIs comes mostly from vendor or secondary sources and is flagged where that applies.

---

## Q1. Carrier waybill and tracking barcodes, UPU S10, GS1 SSCC / GS1-128, GS1 Digital Link and Sunrise 2027

### Takeaway
A parcel hub sees three kinds of item identifier side by side:
- **Carrier-proprietary tracking numbers**, usually in Code 128, often with a 2D carrier symbol (UPS MaxiCode, FedEx PDF417).
- **UPU S10 13-character IDs** on international postal items, in Code 128 or Code 39.
- **GS1 SSCCs** (18 digits, AI 00) in GS1-128 on GS1 logistic labels.

Containers have their own schemes. One example is the UPU S9 29-character receptacle ID for postal bags. GS1 "Sunrise 2027" is a retail point-of-sale (POS) programme, not a parcel-label mandate. Even so, the GS1 Logistic Label Guideline (since Release 1.3, 2019) allows a supplementary GS1 DataMatrix or QR code next to the mandatory GS1-128.

### Cited Findings

**UPU S10 (postal item identifier)**
- **Version:** UPU S10-12, "Identification of postal items – 13-character identifier". UPU status 2, adopted 10 May 2011; this version approved 17 Oct 2017; © UPU 2018. The UPU says to check the Catalogue of UPU Standards for the current version — [UPU S10-12](https://upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S10-12.pdf)
- **Structure:**
  - Characters 1–2: service indicator.
  - Characters 3–10: serial number (8 digits).
  - Character 11: check digit.
  - Characters 12–13: ISO country code of the issuing operator.
  - Example: CP654321092GM, a parcel from Gambia — [UPU S10-12](https://upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S10-12.pdf)
- **Check digit:** "weighted modulus 11" with weights 8 6 4 2 3 5 9 7. The steps are: sum the weighted digits, take the sum mod 11, subtract from 11; a result of 10 becomes 0 and 11 becomes 5. Worked example: 47312482 → 473124829 — [UPU S10-12](https://upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S10-12.pdf)
- **Service indicators:**
  - EA–EZ = EMS (EX–EZ need bilateral agreement).
  - CA–CZ = parcel post.
  - Letter-post precedence: insured VA–VZ, then registered RA–RZ, then tracked LA–LZ, then M-bag MA–MZ, then IBRS QA–QM, then other goods UA–UZ.
  - Reserved to avoid clashing with ISO/IEC 15418 data identifiers: JA–JZ, KA–KZ, SA–SZ, TA–TZ, WA–WZ.
  - Operators may let large customers issue their own S10 IDs from allocated ranges.
  — [UPU S10-12](https://upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S10-12.pdf)
- **Symbology:** "use shall be made of either Code 128 … or Code 39 … Code 128 is strongly recommended". Operators must be able to scan both. S10-12 names no 2D symbology — [UPU S10-12](https://upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S10-12.pdf)
- **Possible newer revision (unverified):** a search summary of the UPU version history mentioned a later addition of FA–FZ for proof of delivery in a 2026 revision. I did not verify this in the primary document — [UPU Technical Standards version history](https://www.upu.int/UPU/media/upu/documents/Standards/UPU-Technical-Standards-version-history.pdf)

**GS1 SSCC and GS1-128 logistic label**
- **SSCC structure:** 18 digits = extension digit (0–9) + GS1 Company Prefix + serial reference (together 17 digits) + check digit. The check digit uses the standard GS1 mod-10 method, as for GTIN and GLN — [GS1 UK](https://www.gs1uk.org/support-training/help-to-use-and-implement-gs1-standards/logistics-labels-and-ssccs); [GS1 UK how-to PDF](https://www.gs1uk.org/sites/default/files/94702_HowToGuideslogistics%20labels%20and%20SSCCs_0315_FV.pdf)
- **Barcode and reuse:** AI (00) always introduces the SSCC, which is carried in GS1-128. GS1 UK says an SSCC may be reused 1 year after it was last used in communications. GS1 Australia says it can identify "a case, pallet or parcel" — [GS1 UK](https://www.gs1uk.org/support-training/help-to-use-and-implement-gs1-standards/logistics-labels-and-ssccs); [GS1 AU](https://www.gs1au.org/standards/id-keys/sscc)
- **Guideline version:** GS1 Logistic Label Guideline, Release 1.3, Ratified, Jul 2019. A label without an SSCC is not a GS1 Logistic Label — [GS1 Logistic Label Guideline 1.3](https://ref.gs1.org/guidelines/logistic-label/); [gs1.org page](https://www.gs1.org/standards/gs1-logistic-label-guideline)
- **Label layout, building blocks:**
  - Top: free text and graphics, such as addresses and logos.
  - Middle: non-HRI text with data titles.
  - Bottom: barcodes with HRI. "Only the bottom building block is mandatory."
  - Up to three segments: supplier, customer and carrier. The carrier (transport) segment typically holds ship-to postal code AI (420), GINC AI (401) and the routing code AI (403). The routing code's "content and structure are at the discretion of the carrier".
  — [GS1 Logistic Label Guideline 1.3](https://ref.gs1.org/guidelines/logistic-label/)
- **2D on logistic labels:** "GS1 Logistic Labels have always used GS1-128 barcodes, but this version of the guideline introduces the use of supplementary GS1 2D barcodes." The 2D symbol goes to the right of the middle block. Example 10.13 is a parcel label with a GS1 DataMatrix ("a GS1 QR Code would also be acceptable"). Concatenation "shall not be used with SSCC … on A6 / 4x6 labels" — [GS1 Logistic Label Guideline 1.3](https://ref.gs1.org/guidelines/logistic-label/)

**Carrier symbologies (secondary sources)**
- **UPS MaxiCode:** ISO/IEC 16023, developed by UPS in 1987, a hexagonal dot grid with a bull's-eye.
  - Mode 2 is the structured carrier message for domestic shipments and Mode 3 for international.
  - It encodes postal code, country, class of service, tracking number, carrier code, shipper number and pickup day, using GS (ASCII 29) separators and EOT (ASCII 04).
  — [Wikipedia: MaxiCode](https://en.wikipedia.org/wiki/MaxiCode); [BWIPP MaxiCode wiki](https://github.com/bwipp/postscriptbarcode/wiki/MaxiCode)
- **FedEx PDF417:** Zebra's ZPL documentation shows a FedEx Ground label using PDF417, a stacked 2D code that can hold >1000 bytes. I did not retrieve FedEx's current label specification — [Zebra PDF417](https://support.zebra.com/cpws/docs/zpl/pdf417_barcode.htm)
- **USPS IMpb:** generally follows GS1-128.
  - Routing part: AI 420 + 5- or 9-digit ZIP.
  - Then a channel AI (91 legacy; 92/93 commercial mailers; 94 PC Postage; 95 retail), a 3-digit service type code, a 6- or 9-digit Mailer ID and a serial.
  - Total length is 22–34 digits.
  - The figures come from the archived DMM 204 (2021) and secondary guides, so check the current DMM.
  — [USPS DMM 204 (archive 2021)](https://pe.usps.com/Archive/NHTML/DMMArchive20211003/204.htm); [Neodynamic](https://www.neodynamic.com/barcodes/USPS-IMbp-Intelligent-Mail-Package-Barcode.aspx); [Federal Register 2010](https://www.govinfo.gov/content/pkg/FR-2010-09-17/html/2010-23313.htm)

**GS1 Digital Link and Sunrise 2027**
- **Digital Link URI for an SSCC:** the SSCC can be expressed as a Digital Link URI with path `/00/`, for example `https://id.gs1.org/00/106141412345678908?02=00614141123452&37=25&10=ABC123` (SSCC + content GTIN + count + batch). This example comes from third-party library documentation. The normative spec is GS1 Digital Link URI Syntax (Release 1.4.0, Jun 2023 was found; I did not confirm whether newer releases exist) — [biip docs](https://biip.readthedocs.io/stable/reference/gs1_digital_link_uris/); [GS1 DL URI Syntax 1.4.0](https://ref.gs1.org/standards/digital-link/uri-syntax/1.4.0)
- **Sunrise 2027 scope:** GS1 US describes Sunrise 2027 as a retail POS transition to 2D (QR with GS1 Digital Link, GS1 DataMatrix). Full 2D capability by 2027 is not required. The page does not address logistics or shipping labels — [GS1 US Sunrise 2027](https://www.gs1us.org/industries-and-insights/by-topic/sunrise-2027)
- **Announcement:** GS1 announced the 2D "sunrise" at the GS1 Global Forum in Brussels in Feb 2023 (trade press) — [The Manufacturer](https://www.themanufacturer.com/articles/the-rise-of-2d-barcodes/); [Packworld](https://www.packworld.com/design/package-design/article/22885258/2027-the-target-for-transition-away-from-1d-gtin-toward-digital-link-2d-barcodes)

**UPU S9 (receptacle ID)** — see Q3.

### Inferences
- **Multiple identifiers per parcel:** a hub event model should not assume one identifier per parcel. One parcel can carry a carrier tracking number, an S10, an SSCC and a retailer reference at the same time. Model `identifiers[]` with a scheme tag (`s10`, `sscc`, `carrier:<scac>`, `impb`, `dl-uri`), and normalise SSCCs and S10s to EPC URN or Digital Link URI forms for EPCIS.
- **Check digits:** S10 (mod 11) and SSCC (mod 10) check digits allow cheap validation of OCR or vision-decoded identifiers before fusion. A vision pipeline reading the human-readable text can reject impossible strings.
- **Sunrise 2027 relevance:** it matters mostly indirectly: more 2D symbols will appear on items inside parcels and as supplementary codes on logistic labels. The primary sort identifiers on parcels remain 1D Code 128 / GS1-128 plus carrier 2D symbols.

### Gaps
- No primary FedEx or UPS label specification was retrieved. The MaxiCode field list comes from secondary sources.
- I did not confirm a newer release than 1.3 (2019) of the GS1 Logistic Label Guideline, or than 1.4.0 of Digital Link URI Syntax.
- The S10 FA–FZ (2026) addition is unverified.
- I found no GS1 primary statement on 2D or Digital Link specifically for parcel carriers (gs1.org returned 403).

---

## Q2. Label damage and no-reads: first-pass read rates and causes

### Takeaway
Vendors advertise read rates of about 99.9% for multi-sided camera tunnels. The only operator figure I found (an MIT thesis on Amazon) reports average tunnel read rates of about 80–90% at large crossbelt sorter sites, against a 98% target. Causes of no-reads are mostly label and presentation problems rather than the reader itself. Systems typically store no-read images for root-cause analysis, which is directly relevant to CCTV fusion.

### Cited Findings
- **Amazon, operator data:** MIT thesis (Felix Dumont, June 2021), *Deep Learning Models of Scanner/Vision Tunnel Performance in Sortation Subsystems*:
  - Amazon's large crossbelt sorter sites average "around 80-90% read rate success" against a 98% target.
  - Amazon had "little visibility" into no-read causes across sites.
  - The project sent no-read scanner images to AWS and classified fault reasons with ResNet models tuned by Bayesian optimisation.
  - Estimated savings of about $2.2M per year for the pilot sites.
  — [MIT DSpace](https://dspace.mit.edu/handle/1721.1/139395)
- **Cognex, vendor claim:** a 99.9% read rate for its five-sided tunnels. On no-reads the system stores "the code images for later root cause analysis". Treat this as marketing; I could not re-fetch the page (HTTP 429), and the claim reached me via search summary — [Cognex ship sorter scanning](https://www.cognex.com/industries/logistics/sortation/ship-sorter-scanning)
- **Vitronic, vendor blog (updated 19 Feb 2026):**
  - Listed causes: glare, background interference, wrong label placement, low print quality, low contrast, bar growth, voids, folded, wrinkled or glossy labels, dirt, skewed labels, distorted printing and partially damaged or ripped labels.
  - Belt speeds "exceed 3 meters per second".
  - It frames the goal as first-time reads (FTR) and gives no percentage.
  — [Vitronic](https://www.vitronic.com/en-us/blog/smart-logistics/inbound-scanning-performance)
- **Inbound Logistics, trade press:**
  - Labels "fold around the edges of boxes", or are wrinkled, glossy or partially damaged; print quality drops when printers need maintenance; high conveyor speeds and odd angles cause perspective distortion.
  - Laser scanners see one scan line, so they struggle with degraded or angled codes.
  - A typical tunnel uses six readers (top, bottom, two sides, front, back).
  - The article also contains a "2 to 5 percent" laser read-rate figure that looks like a misprint or a different metric. Do not use it.
  — [Inbound Logistics](https://www.inboundlogistics.com/articles/tunnel-scanning-in-consolidation-warehouses/)
- **BEUMER, "unsolvable" parcels:** a "no-read" may be a parcel whose barcode is readable but whose data is non-compliant or unresolvable ("readable, but unsolvable"). This distinguishes read rate from solve rate — [BEUMER knowledge (Jan Schroeder)](https://knowledge.beumergroup.com/cep/ecommerce-labelling-parcels)

### Inferences
- **Separate the failure modes:** the event model should distinguish at least four outcomes:
  - `no_read`: no symbol decoded.
  - `no_solve`: decoded, but no matching or valid record.
  - `multi_read`: conflicting codes on one item.
  - `read`.

  Tunnel no-read images are natural evidence to attach. EPCIS explicitly allows an ObjectEvent to assert that "an expected observation failed to occur" (see Q4).
- **Fusion gap:** an 80–90% field read rate versus 99.9% marketing claims means 10–20% of items at some sites may need non-barcode identification or tracking, such as CCTV re-identification or dimension and weight matching. That is the opportunity for camera fusion. It is an inference from a single operator source.
- **Poly-mailers and multiple labels:** the gathered sources name these only indirectly (glossy, wrinkled, folded labels; multiple codes). I found no quantified independent breakdown.

### Gaps
- No independent, published breakdown of no-read causes by share (for example % damaged vs % no label vs % poly-mailer).
- No SICK, Datalogic, Zebra or Honeywell figures were retrieved (tool budget).
- The Amazon figure is from 2021 and covers one operator.

---

## Q3. Consolidation: bags, cages, roll containers, gaylords, ULDs, trailers, and nesting

### Takeaway
Container IDs are scanned the same way as items (barcode on a bag label, cage tag or trailer placard). Item-to-container membership is recorded by "nesting" scans: item → bag, bag → cage or despatch, cage → trailer. In EPCIS, this is an AggregationEvent: ADD to build, DELETE to break down, OBSERVE to see it unchanged. Its semantics imply that children share the parent's location until disaggregation. That is exactly the rule for inferring a parcel's location from its container's scans.

### Cited Findings
- **S9 receptacle ID:** UPU S9 "Postal receptacle identifier" (version approved 30 Oct 2014; the text calls itself "the ninth version", while the PDF metadata says S9-8, which is inconsistent) defines a 29-character receptacle ID that is unique within the postal industry for 10 years.
  - Positions 1–20: Despatch ID (per S8). This breaks down as:
    - 1–6: origin IMPC code.
    - 7–12: destination IMPC code.
    - 13: mail category.
    - 14–15: mail subclass.
    - 16: despatch year (last digit).
    - 17–20: despatch number.
  - 21–23: receptacle serial within the despatch (001–999).
  - 24: highest-numbered-receptacle indicator (0/1/9).
  - 25: registered/insured indicator (0/1/9).
  - 26–29: gross weight in hectograms (9999 if >999.8 kg).
  - Example despatch ID: DEFRAANLAMSAAUN40027.
  — [UPU S9](https://upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S09TechnialStandard.pdf)
- **Bag-tag scanning:** S9 notes that transit operators can assign receptacles to delivery bills "by scanning the barcoded receptacle ID" — [UPU S9](https://upu.int/UPU/media/upu/files/postalSolutions/programmesAndServices/standards/S09TechnialStandard.pdf)
- **UPU message levels:** EMSEVT V3 (M40) is item-level. PREDES and RESDES are the receptacle-level messages. Receptacle event codes (code list 119) belong to RESDES. Nesting of small packets inside receptacles is expressed in PREDES — [UPU Annex 3-1 general technical information](https://www.upu.int/UPU/media/upu/TPC_CAA/RFPs/2020/Annex-3-1_General-technical-information.docx); [UPU nesting of small packets in PREDES](https://www.upu.int/UPU/media/upu/documents/Standards/Nesting-of-small-packets-in-PREDES_FR.pdf)
- **GS1 logistic units:** SSCC identifies any logistic unit ("case, pallet or parcel"). The GS1 label guideline covers placement on "larger logistic units (pallets, roll cages, etc.)". GINC (AI 401) identifies a consignment and "holds the Master Way Bill (MWB) Number, for example a Master Airway Bill" — [GS1 AU](https://www.gs1au.org/standards/id-keys/sscc); [GS1 Logistic Label Guideline 1.3](https://ref.gs1.org/guidelines/logistic-label/)
- **EPCIS AggregationEvent purpose:** used for "a strong physical relationship between the containing and the contained objects such that they will all occupy the same location at the same time, until such time as they are disaggregated". It is not for weaker relationships, such as two pallets in the same shipment; TransactionEvent may suit those — [EPCIS 2.0 §7.4.3](https://ref.gs1.org/standards/epcis/)
- **AggregationEvent actions:**
  - **ADD:** children aggregated to the parent, either creating the aggregation or adding to it.
  - **OBSERVE:** no change. "The observation may be incomplete: there may be children … not observed … likewise, the parent identity may not be observed or known … and therefore the parentID field [may] be omitted."
  - **DELETE:** children removed. "Both childEPCs and childQuantityList field may be omitted … which means that all children have been disaggregated."
  - `parentID` is required for ADD and DELETE and optional for OBSERVE.
  — [EPCIS 2.0 §7.4.3](https://ref.gs1.org/standards/epcis/)
- **Location inheritance:** AggregationEvent `bizLocation` is "the business location where the aggregated objects … may be found, until contradicted by a subsequent event" — [EPCIS 2.0 §7.4.3](https://ref.gs1.org/standards/epcis/)
- **AssociationEvent (new in 2.0):** for associating objects with a parent object *or a physical location*, and for more permanent associations, such as sensors installed in a returnable transport item or a wagon assembly, which then also appear in temporary AggregationEvents. The standard's illustration pairs:
  - Association ADD = assembling.
  - Aggregation ADD = loading.
  - Aggregation DELETE = unloading.
  - Association DELETE = removing.
  — [EPCIS 2.0 §7.4.6](https://ref.gs1.org/standards/epcis/)
- **Transfer business steps:** CBV describes a multi-step business transfer as "loading → departing → transporting → arriving → unloading → accepting" (quoted in EPCIS §7.3.6.4) — [EPCIS 2.0](https://ref.gs1.org/standards/epcis/)

### Inferences
- **Mapping hub nesting to EPCIS:**
  - Parcel into bag or cage = AggregationEvent ADD (parent = bag S9 or SSCC; children = parcel IDs).
  - Cage onto trailer = AggregationEvent ADD (parent = trailer or ULD ID).
  - Trailer unload = DELETE, then per-container DELETE at break-down.
  - Location inference: a parcel's current location is the latest `bizLocation` of its innermost container, unless a direct item event postdates it. Resolve this recursively up the nesting tree.
- **A lever for CCTV:** a camera that sees a cage enter a trailer without seeing parcel labels can emit an AggregationEvent OBSERVE with `parentID` only (children omitted). This is explicitly allowed. A camera that sees parcels go into an unidentified cage can emit OBSERVE with children and no `parentID`.
- **Location-level association:** AssociationEvent's support for location parents lets the model associate a cage with a dock door or staging lane.
- **Container ID schemes:** gaylords, roll cages and reusable cages are usually identified by GRAI (returnable asset) or carrier-internal IDs; ULDs by IATA ULD codes; trailers by SCAC plus trailer number. These schemes were not verified in this research (see Gaps).

### Gaps
- No primary source retrieved for GRAI on roll cages, for IATA ULD ID format, or for carrier-internal bag, gaylord or trailer identifiers.
- No field-level PREDES or RESDES layout. The UPU M41/M48-series message specs are not public.
- No operator documentation on how nesting scans are enforced in practice (for example, a mandatory close-out "container_closed" scan).

---

## Q4. GS1 EPCIS 2.0 and CBV 2.0: exact fields and vocabularies

### Takeaway
EPCIS 2.0 (ratified Jun 2022; latest edition 2.0.1, 1 Jul 2025) and CBV 2.0 define five event types over what/when/where/why plus a new "how" dimension (`sensorElementList`). Field names below were checked against the standard text. Note that CBV 2.0 has no `sorting` business step; hub sorting must use a custom bizStep URI or a nearby standard step.

### Cited Findings

**Versions**
- EPCIS Standard "Release 2.0, Ratified, Jun 2022" (229 pp.); CBV Standard "Release 2.0, Ratified, Jun 2022" (124 pp.) — [EPCIS 2.0](https://ref.gs1.org/standards/epcis/); [CBV 2.0](https://ref.gs1.org/standards/cbv/)
- The GS1 archive lists EPCIS 2.0.1 (1 Jul 2025, latest), 2.0.0 (22 Jun 2022), 1.2.0 (29 Sep 2016), 1.1.0 (20 May 2014), 1.0.1 (2007) and 1.0.0 (2007). CBV paired with 2.0.x is 2.0.0 — [EPCIS archive](https://ref.gs1.org/standards/epcis/archive)
- A secondary source says EPCIS 2.1 is in progress for end-2026. This is unverified; the GS1 archive page does not mention it — [search summary citing Wikipedia](https://en.wikipedia.org/wiki/EPCIS)
- **New in 2.0:** JSON/JSON-LD binding, REST interface, the "How" dimension (SensorElement), persistentDisposition, certificationInfo on the core EPCISEvent, AssociationEvent, and Digital Link URIs accepted alongside EPC URNs — [EPCIS 2.0](https://ref.gs1.org/standards/epcis/)

**Event types**
ObjectEvent, AggregationEvent, TransactionEvent, TransformationEvent and AssociationEvent. All are subclasses of EPCISEvent — [EPCIS 2.0 §7.4](https://ref.gs1.org/standards/epcis/)

**EPCISEvent common fields (§7.4.1)**
- `eventTime` (xsd:dateTimeStamp): "The date and time at which the EPCIS Capturing Applications asserts the event occurred."
- `recordTime` (optional): the time "at which this event was recorded by an EPCIS Repository". It "SHALL be ignored when an event is presented to the EPCIS Capture Interface" and "SHALL be present" on query. It is "a bookkeeping mechanism" for standing queries.
- `eventTimeZoneOffset` (string `±hh:mm`, range -14:00 to +14:00): the local offset "in effect at the time and place the event occurred". It is business context only; `eventTime` alone fixes the instant.
- `eventID` (optional): globally unique. CBV specifies a UUID URI or NI hash URI.
- `errorDeclaration` (optional), containing:
  - `declarationTime`
  - `reason` (CBV error reasons such as `did_not_occur`, `incorrect_data`)
  - `correctiveEventIDs`

  An error declaration repeats the erroneous event exactly. Events are never deleted or modified.
- `certificationInfo` (optional): "a URL at which certification details can be found", using `gs1:CertificationDetails` from the GS1 Web Vocabulary.

— [EPCIS 2.0 §7.4.1](https://ref.gs1.org/standards/epcis/)

**ObjectEvent fields (§7.4.2)**
- `epcList`, `quantityList`, `action`, `bizStep`, `disposition`, `persistentDisposition`, `readPoint`, `bizLocation`, `bizTransactionList`, `sourceList`, `destinationList`, `sensorElementList`, `ilmd`.
- **ADD:** the objects were commissioned (IDs issued for the first time).
- **OBSERVE:** "a simple observation … not their commissioning or decommissioning".
- **DELETE:** decommissioned. The objects "SHOULD NOT appear in subsequent events".
- ObjectEvent can be used "for any event a Capturing Application wants to assert about objects, including … capturing the fact that an expected observation failed to occur."

— [EPCIS 2.0 §7.4.2](https://ref.gs1.org/standards/epcis/)

**AggregationEvent fields (§7.4.3)**
`parentID`, `childEPCs`, `childQuantityList`, `action`, `bizStep`, `disposition`, `readPoint`, `bizLocation`, `bizTransactionList`, `sourceList`, `destinationList`, `sensorElementList`. Action semantics are in Q3. TransactionEvent uses `parentID` (optional), `epcList`, `quantityList`, `bizTransactionList` (required) and `action`. TransformationEvent has no action and uses input and output lists (`outputEPCList`, `outputQuantityList`) — [EPCIS 2.0](https://ref.gs1.org/standards/epcis/)

**The Action type (§7.3.2)**
An enumeration ADD / OBSERVE / DELETE. Action "is not a vocabulary type, and SHALL NOT be extended by industry groups." Action is independent of `bizStep` — [EPCIS 2.0 §7.3.2](https://ref.gs1.org/standards/epcis/)

**Where: readPoint vs bizLocation (§7.3.5)**
- **ReadPoint:** "the most specific place at which an EPCIS event took place … 'where objects were at the time of the EPCIS event.'" The capturing application determines it, for example from a stationary logical reader or by reading a location tag.
- **BusinessLocation:** "where an object is assumed to be following an EPCIS event until it is reported to be at a different Business Location", i.e. "where objects are following the EPCIS event."
- Read points support retrospective semantics; business locations support prospective ones.
- Both are user vocabularies, typically SGLN URIs, but non-EPC URIs are allowed.
- Physical and logical reader IDs were deliberately left out of events as "of little interest to trading partners".

— [EPCIS 2.0 §7.3.5](https://ref.gs1.org/standards/epcis/)

**Why: disposition and persistentDisposition**
- `disposition` is the business condition after the event, "assumed to hold true until another event indicates a change". Events with no disposition have no effect on it.
- `persistentDisposition` values are set or unset independently and persist until explicitly unset.

— [EPCIS 2.0 §7.3.6.2](https://ref.gs1.org/standards/epcis/)

**How: SensorElement (§7.3.7.1)**
- A `sensorElement` contains at most one `sensorMetadata` and one or more `sensorReport`s.
- **sensorMetadata fields:** `time`, `startTime`, `endTime`, `deviceID`, `deviceMetadata`, `rawData`, `dataProcessingMethod`, `bizRules`.
  - Sensor `time` must be ≤ `eventTime` and include a timezone offset.
  - Capture applications "SHOULD apply established time synchronisation protocols such as IEEE 1588-2008".
- **sensorReport fields:** `type` (CBV MeasurementType as `gs1:X` or a custom URI), `exception` (SensorAlertType), `deviceID`, `deviceMetadata`, `rawData`, `dataProcessingMethod`, `time`, `microorganism`, `chemicalSubstance`, `value`, `component`, `stringValue`, `booleanValue`, `hexBinaryValue`, `uriValue`, `minValue`, `maxValue`, `meanValue`, plus `uom` and others.
- EPCIS "SHOULD NOT be used to accommodate raw sensor data". Instead, "include a Web URI in the rawData element, pointing to a resource through which clients can access the underlying raw sensor data."
- `dataProcessingMethod` points to a document describing the algorithm used to refine data.
- `component` allows coordinate components (x, y, z; latitude, longitude; and others).

— [EPCIS 2.0 §7.3.7.1](https://ref.gs1.org/standards/epcis/)

**CBV 2.0 business steps (verified present in the bizStep table)**
accepting, arriving, assembling, collecting, commissioning, consigning, creating_class_instance, cycle_counting, decommissioning, departing, destroying, disassembling, dispensing, encoding, entering_exiting, holding, inspecting, installing, killing, loading, other, packing, picking, receiving, removing, repackaging, repairing, replacing, reserving, retail_selling, sampling, sensor_reporting, shipping, staging_outbound, stock_taking, stocking, storing, transporting, unloading, unpacking, void_shipping. **`sorting` does not appear** — [CBV 2.0 §7.1.3](https://ref.gs1.org/standards/cbv/)

Selected definitions:
- **loading:** "an object is loaded into shipping conveyance."
- **unloading:** "an object is unloaded from a shipping conveyance."
- **arriving:** "an object arrives at a location."
- **accepting:** "an object changes possession and/or ownership."
- **receiving:** "an object is being received at a location and is added to the receiver's inventory."
- **shipping:** "Indicates the overall process of staging_outbound, loading, departing, and accepting." It is used when finer steps are unknown and is mutually exclusive with staging_outbound, departing or loading.
- **transporting:** "moving an object from one location to another using a vehicle."
- **sensor_reporting:** "SHOULD only be used when no other business step is in progress."

— [CBV 2.0](https://ref.gs1.org/standards/cbv/)

**CBV 2.0 dispositions (verified present)**
active, available, completeness_inferred, completeness_verified, conformant, container_closed, container_open, damaged, destroyed, dispensed, disposed, encoded, expired, in_progress, in_transit, inactive, mismatch_class, mismatch_instance, mismatch_quantity, needs_replacement, no_pedigree_match, non_conformant, non_sellable_other, partially_dispensed, recalled, reserved, retail_sold, returned, sellable_accessible, sellable_not_accessible, stolen, unavailable, unknown.

Selected definitions:
- **in_progress:** "Optional disposition for object proceeding through points in the supply chain."
- **in_transit:** "Object being shipped between two trading partners."
- **container_closed:** "Object has been loaded onto a container, the doors have been closed and the shipment sealed."

— [CBV 2.0 §7.2.3](https://ref.gs1.org/standards/cbv/)

**Custom vocabulary**
The EPCIS 2.0 REST examples use non-CBV bizStep values in compact-URI form, for example `/bizSteps/ex1:qualityCheck/events` and `vendor2:QA`. This shows that custom business steps are expected — [EPCIS 2.0 §12 REST](https://ref.gs1.org/standards/epcis/)

**Bindings and interfaces**
- JSON-LD context: `https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld`. Validation uses JSON Schema and SHACL.
- REST resources: `/capture`, `/capture/{captureID}`, `/events`, `/eventTypes/{eventType}/events`, `/epcs/{epc}/events`, `/bizSteps/{bizStep}/events`, `/queries`. Query example: `/eventTypes/ObjectEvent/events?EQ_bizStep=shipping`.
- An OpenAPI description is published at ref.gs1.org.
- Events in JSON use `"type": "ObjectEvent"` and similar.

— [EPCIS 2.0 §10, §12](https://ref.gs1.org/standards/epcis/)

### Inferences
- **bizStep for sort and induct scans:** use a namespaced custom bizStep, for example `https://<org>/voc/bizstep/sorting` or `urn:<org>:bizstep:induct`. Alternatively, use the nearest CBV steps (`arriving`, `loading`, `unloading`, `staging_outbound`, `holding`) and keep sort-specific detail in extension fields.
- **No-reads:** model them as an ObjectEvent OBSERVE whose "what" is unknown. EPCIS requires at least one of `epcList` or `quantityList`, so you may need a placeholder class or an extension, or report it as a sensor exception. Alternatively, treat no-reads as non-EPCIS internal events. The "expected observation failed to occur" wording supports the ObjectEvent route.
- **Capture discipline:** `eventTime` = when the observation happened, synchronised clocks (IEEE 1588 / PTP recommended for sensors); `recordTime` = ingest; `eventTimeZoneOffset` = hub local offset. This maps cleanly to video timestamps, provided camera clocks are synchronised.
- **Corrections:** correcting a fused or inferred event later should use `errorDeclaration` with `correctiveEventIDs`, not mutation. This gives an audit trail for investigations.

### Gaps
- Not verified: CBV 2.0 full definition text for `damaged`, `unknown` and `completeness_inferred`. The PDF tables did not extract cleanly; the values are confirmed present.
- I did not check the differences between 2.0.0 and 2.0.1 (errata versus substantive changes).
- EPCIS 2.1 scope and timing are unconfirmed.

---

## Q5. Carrier tracking event models in practice; UPU EDI (EMSEVT, ITMATT)

### Takeaway
Carrier APIs and UPU EDI share a simple flat event shape: item ID + event code + timestamp + location + optional reason or exception code. The EMS minimum event set (EMA … EMI) is the clearest public standard vocabulary. Carrier APIs (FedEx `scanEvents`, UPS `activity`) follow the same pattern, but I could not retrieve primary documentation in this session.

### Cited Findings
- **EMS minimum events:** operators "shall use UPU standard M 40–EMSEVT V3" for all EMS items. The minimum set is:
  - EMA: posting/collection.
  - EMB: arrival at outward office of exchange.
  - EMC: departure from outward office of exchange.
  - EMD: arrival at inward office of exchange.
  - EDB: item presented to import customs.
  - EME: held by import customs.
  - EDC: item returned from customs (import).
  - EMF: departure from inward office of exchange.
  - EMH: unsuccessful (physical) delivery.
  - EMI: final delivery.

  "Full track and trace" adds PREDES and RESDES messages. Events EXD, EXX, EDA, EDF, EDX and EMH "should include appropriate reason codes". Events carry mandatory (M), conditionally mandatory (MC) and recommended (R) elements per the M40 IT Guide. Operators should also send postcode or delivery-zone information — [UPU EMS Standards 2017 training deck](https://www.ems.post/sites/default/files/content-block-files/EMS%20Standards%202017.pdf)
- **Code lists:** EMSEVT is tied to UPU code lists 108 (IMPC codes), 112 (item event reason codes) and 113 (item event action-taken codes). Receptacle event codes (list 119) belong to RESDES — [UPU Annex 3-1](https://www.upu.int/UPU/media/upu/TPC_CAA/RFPs/2020/Annex-3-1_General-technical-information.docx); [UPU mail subclasses / code lists](https://upu.int/UPU/media/upu/documents/Standards/Mail-subclasses-and-handling-classes_purpose-and-usage_AN.pdf)
- **Repeated events:** UPU compliance notes define a repeated EMSEVT event as one with the same item identifier, event code, location code and origin and destination EDI addresses. These keys are useful for deduplication — [UPU EMSEVT repeated events note](https://upu.int/getmedia/405ea48f-01e3-4a6c-86f2-611142cf619c/complianceWithUpuStandardsExplanatoryNotesEMSEVTRepeatedEventsEn.pdf)
- **FedEx Track API (third-party description, not primary):**
  - `latestStatusDetail`: two-letter code such as DL, IT or SE, plus description and location.
  - `scanEvents[]`: newest first, each with date, `eventType`, `eventDescription`, `scanLocation` (city, state, country, postal code) and optional `exceptionCode` / `exceptionDescription` and delay details.
  - Exception examples, from a vendor KPI page and unverified: 07, 09, 12, 17, 67, 70, 80, 83, 84.
  — [Blink Ops FedEx integration docs](https://docs.blinkops.com/docs/integrations/fedex/actions/track-by-references.md); [Vortex IQ](https://docs.vortexiq.ai/nerve-centre/kpi-cards/fedex/exception-rate)
- **AfterShip normalisation:** AfterShip publishes a normalised cross-carrier event enum (for example `delivery_attempt_failed`), versioned (2025-01, 2025-07, 2026-07). This shows aggregators map carrier codes to a common checkpoint vocabulary — [AfterShip events enum](https://www.aftership.com/docs/tracking/2026-07/enum/events)

### Inferences
- **Common event schema:** a minimal hub event should carry `item_id`, `id_scheme`, `event_code` (internal) plus `epcis_bizStep` / `disposition` mapping, `event_time` with offset, `record_time`, `location_code` (facility, then readPoint), `reason_code`, `container_id` and `source` (scanner, camera, manual). This covers EMSEVT, carrier APIs and EPCIS.
- **Reason and action codes:** the UPU separation of *reason* codes (list 112) from *action taken* codes (list 113) is a useful pattern for exception events such as damaged label or missort.

### Gaps
- No primary UPS Tracking API documentation (developer.ups.com returned 403) and no primary FedEx API reference. Field names above are from third parties.
- No field-level EMSEVT V3, ITMATT or CARDIT data-element tables. UPU M-series message specs are distributed to members and are not public. ITMATT (item attribute and customs pre-advice) was not covered by any retrieved source.

---

## Q6. Mapping CCTV observations to EPCIS; prior art for video evidence linked to EPCIS events

### Takeaway
EPCIS 2.0 has no camera- or video-specific construct, and I found no published prior art (GS1 guidance, papers or products) linking video or image evidence to EPCIS events. The standard does provide clean hooks:
- `readPoint` = camera field-of-view zone.
- `action: OBSERVE`.
- `sensorElementList` with `deviceID` = camera, `rawData` = URI of the clip or frame, and `dataProcessingMethod` = URI of the CV model card.
- The confidence score in `sensorReport` value fields.
- An optional custom namespace for detection details.
- `certificationInfo` or a hash for evidence integrity.

### Cited Findings
- **Read point determination:** EPCIS lets the capturing application determine the read point "by any other means the EPCIS Capturing Application chooses to use". Read and business location IDs need not be EPCs, which lets "organisations … reuse existing ways of naming locations" — [EPCIS 2.0 §7.3.5](https://ref.gs1.org/standards/epcis/)
- **Raw-data link:** sensor `rawData` is a "Storage/service location of the raw sensor data on which the aggregated/business-oriented data contained in the sensorElement is based". GS1 advises linking raw data by URI rather than embedding it — [EPCIS 2.0 §7.3.7.1](https://ref.gs1.org/standards/epcis/)
- **Processing method and device:** `dataProcessingMethod` is "Storage location of an electronic document accommodating the data processing method … the latter might be redacted or refined by means of specific algorithms". `deviceID` (EPC) and `deviceMetadata` (URI) identify the source device — [EPCIS 2.0 §7.3.7.1](https://ref.gs1.org/standards/epcis/)
- **Value fields:** sensorReport offers `stringValue`, `uriValue`, `booleanValue`, `value`, `minValue`/`maxValue`/`meanValue` and `component` (x, y, z coordinates). `type` may be a custom URI if no CBV MeasurementType fits — [EPCIS 2.0 §7.3.7.1.2](https://ref.gs1.org/standards/epcis/)
- **Partial observations:** AggregationEvent OBSERVE allows an incomplete observation, with children or parent omitted. ObjectEvent may record that "an expected observation failed to occur" — [EPCIS 2.0 §7.4.2–7.4.3](https://ref.gs1.org/standards/epcis/)
- **Clock synchronisation:** sensor `time` ≤ `eventTime`, with IEEE 1588-2008 synchronisation recommended — [EPCIS 2.0 §7.3.7.1.1](https://ref.gs1.org/standards/epcis/)
- **No video terms in the standards:** a text search of the EPCIS 2.0 and CBV 2.0 PDFs for "image", "video", "camera" and "photo" returned no normative constructs (my check of the downloaded texts) — [EPCIS 2.0](https://ref.gs1.org/standards/epcis/); [CBV 2.0](https://ref.gs1.org/standards/cbv/)
- **Search results:** a web search for EPCIS + camera / computer vision / video evidence found only generic USPTO EPCIS patents (cameras listed as generic devices) and an unrelated "Digital imaging system for evidentiary use" patent (US 7236596) on per-frame timestamping of evidentiary imagery. This is not EPCIS-specific — [USPTO 7236596](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7236596)
- **Closest operator analogue:** tunnel scanners store no-read images for root-cause analysis (Cognex), and Amazon classified no-read images with ResNet models (MIT 2021). Neither is described as linked to EPCIS events — [Cognex](https://www.cognex.com/industries/logistics/sortation/ship-sorter-scanning); [MIT DSpace](https://dspace.mit.edu/handle/1721.1/139395)

### Inferences
These are proposed mappings, not taken from any standard:
- **Camera as read point:** `readPoint.id` = a URI or SGLN extension per camera *zone*, for example `urn:epc:id:sgln:<gcp>.<loc>.CAM07-Z2`. `bizLocation` = the hub area the object is in afterwards (sort lane, cage staging area).
- **Item seen:** an ObjectEvent with `action: OBSERVE` and the object ID resolved by fusion. If the label was not read, use a fusion-assigned provisional ID (for example a UUID-based URI) and later link it to the true ID via an errorDeclaration/correctiveEventIDs pair or an AssociationEvent.
- **Item into or out of a container:** an AggregationEvent ADD or DELETE, with `parentID` = bag, cage or trailer ID when known. Where the camera only sees the container move, use an AggregationEvent OBSERVE with `parentID` only.
- **Evidence block:** one `sensorElement` per camera observation:
  - `sensorMetadata.deviceID` = camera ID.
  - `deviceMetadata` = camera calibration and position doc.
  - `rawData` = URI of the clip or keyframe in a video store; it does not need to be public.
  - `dataProcessingMethod` = URI of the detector or re-ID model version.
  - `startTime` / `endTime` = clip window.
  - `sensorReport`s with custom `type` URIs, for example `ex:detectionConfidence` (`value`), `ex:bbox` (`component` x/y), `ex:labelVisible` (`booleanValue`), `ex:decodedText` (`stringValue`).

  GS1's own guidance (link raw data by URI, describe the processing method) fits evidence links well.
- **Integrity:** store a content hash of the clip in the event, via a custom field or `stringValue`. Optionally point `certificationInfo` at an attestation, though it is meant for certifications such as organic or MSC, so this would be a stretch. Also consider using an NI-hash `eventID`.
- **Confidence and correction:** keep inferred (CCTV-only) events distinguishable from scan-confirmed ones. Options are a custom bizStep or disposition, a `persistentDisposition`, or an extension flag. When a later scan contradicts a CCTV inference, issue an errorDeclaration (`reason` = `incorrect_data`) with `correctiveEventIDs`.
- **Novelty:** because I found no prior art, this mapping appears novel. That is worth stating, but cautiously: absence in a limited search is not proof.

### Gaps
- No GS1 guideline, academic paper or product found that links video or image evidence to EPCIS events. A deeper search of Google Scholar, the GS1 EPCIS/CBV MSWG work items and EPCIS 2.1 drafts could change this.
- I did not check whether EPCIS 2.1 drafts add media or evidence fields.
- Peer-reviewed EPCIS papers (for example from Auto-ID Labs KAIST, contributors to EPCIS 2.0) were not reviewed within the tool budget.
