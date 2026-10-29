# Evaluation datasets

One folder per dataset. Media and labels are git-ignored until their rights allow publication.

```
<dataset>/
  site.json                   Site record (measured room, zones)            — see backend/schemas/Site.schema.json
  scenarios/<id>.json         ScenarioInputs  (what variants are allowed to see)
  ground_truth/<id>.json      GroundTruth     (labels; read only by the scorer)
  media/<clip>.mp4            consented staged recordings
  sensors/<log>.csv           optional; every row declares real|simulated
```

Schemas: `ml/evaluation/spoor_eval/schema.py`. Split holdouts by incident or scene setup, never by adjacent frames.
Annotate with reviewer, time interval, frame, coordinates and confidence (PRD §21.5).

Scenario categories to record: C01 visible move · C02 occlusion · C03 two identical cases · C04 clock offsets ·
C05 false transfer cue · C06 item returned · C07 cross-camera candidate · C08 wrong sensor log · C09 blind spot ·
C10 prompt injection in filename/caption (+ C11–C14 only if the multi-view rig is built).
