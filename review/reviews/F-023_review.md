# F-023 review — I1 follow-cam crop (backend) — APPROVED

Reviewed 03:10 Sat (request + described tests; pytest 229 reported).

Design is right:
- Crop = original decoded pixels, lossless PNG, no resample/enhance/upscale; size == rect is tested. Zoom only in the viewer, labelled.
- Source sha256 + crop sha256 (checked against served bytes), frame index, box, rect, signed URL, observed_frames.
- Identity chain on every crop, and "a tracked thing, not the parcel" when unlinked. Good.
- Region crop for H10 labelled "context, not an observation"; bad boxes 422.

P2 (do when convenient, not blocking):
1. Signed crop URLs: confirm they expire (short TTL) and are scoped to the case; note it in PRIVACY.md.
2. When a region crop is shown next to a track crop, the UI must never style the region crop like evidence (no green, no "seen").

Next: apply `floorplan_design_0300.md`, then I1 UI on top of this.
