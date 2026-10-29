# Evidence schema

Source of truth: `backend/src/spoor/contracts/`. JSON Schemas (for other languages, e.g. the future frontend):
`backend/schemas/*.schema.json`, regenerated with `uv run python scripts/export_schemas.py`.

## Chain of derivation

```
MediaAuthorization ─> MediaAsset(original, sha256) ─> MediaAsset(working proxy, parent=original)
                                  │
            FrameRef{media_id, frame_index, pts_ms, normalized_utc, sync_id, time_uncertainty_ms}
                                  │
Track (per clip) ─> RawObservation (immutable, cites FrameRef + model provenance)
                                  │
             SpatialEstimate (spatial_mode, calibration_id, uncertainty) ─ separate from the observation
                                  │
ObjectInstance <─ TrackAssociation (versioned; confirmed | candidate | unresolved | rejected)
                                  │
Hypothesis (proposed by an agent) ─> HypothesisStatusChange (append-only; decided only by verifier/human)
                                  │
VerifiedFinding (>=1 observation; verifier/human only) ─> ReportRecord (draft -> approved, hashed)
```

## IDs

Every ID has a type prefix (`media_`, `obs_`, `trk_`, `loc_`, `objinst_`, `hyp_`, `finding_`, `rev_`, …) so an
observation ID can never be used where a zone ID is expected. IDs are generated server-side.

## Labels shown to users

| Evidence label | Meaning |
|---|---|
| observed | directly in original footage / sensor source |
| estimated | position or link derived from an observation, with uncertainty |
| hypothesized | possible explanation awaiting discriminating evidence |
| unknown | no adequate observation |
| contradicted | inconsistent with evidence |

| spatial_mode | Basis |
|---|---|
| multiview_xyz | validated overlapping rig triangulation (optional, off) |
| floor_xy | validated floor homography of a floor-contact point |
| anchored_height | item on a measured surface zone (coarse) |
| zone_only | operator-drawn image region of a zone |
| image_only | visible, no trustworthy position |
| unknown | no observation |

## Enforced invariants

Source-free findings rejected · agents cannot decide hypotheses or create findings · append-only tables reject UPDATE
at the database level · writes with unknown referenced IDs rejected · normalized timestamps must cite their clock sync
and uncertainty · derivatives must name parent, method and software version · calibrated confidence must cite its
calibration · positions outside the measured floor rejected.
