#!/usr/bin/env bash
# Scenario batch (QUEUE D2/D3): per scenario x camera: frames (resumable) -> CCTV pass (this camera's lens + OSD
# clock) -> H.265 -> the image sequence is deleted. Stops (and says so) if C: has < 15 GB free.
#   bash assets/hub/render_batch.sh S0 "CAM_07,CAM_13" [2688x1520] [4]
set -u
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
S="$1"; CAMS="$2"; RES="${3:-2688x1520}"; SAMPLES="${4:-2}"  # batch settings (measured 30 Oct): no ray tracing, shadow scale 0.5, 2 samples, exposure 0.2
BLEND="${BLEND:-assets/hub/build/hub_$S.blend}"
# S2 renders on line A layout b (the canonical spec): its own blend, and the owner's S2 gate counts only the collision
# rows the rendered cameras see (Rexton 08:16 Sat; mocap/rows_in_view.py on the same collisions.csv)
if [ "$S" = S2 ] && [ -f assets/hub/build/hub_lineAb_S2.blend ]; then BLEND="${BLEND_S2:-assets/hub/build/hub_lineAb_S2.blend}"; fi
FR="assets/hub/build/_frames/$S"
OUT="assets/hub/build/renders/$S"
mkdir -p "$FR" "$OUT"
# pre-render gate (reviews 006 / 009d, owner rule 30 Oct): the scenario's QA flags and its collision report
# (build/qa/scenarios/<S>_flags.csv, <S>_coll/collisions.csv) must both pass - no override of any kind
FL="assets/hub/build/qa/scenarios/${S}_flags.csv"
CL="${COLL:-assets/hub/build/qa/scenarios/${S}_coll/collisions.csv}"
INVIEW="${INVIEW:-}"  # S2: the rows_in_view json made from $CL
HY="${HYGIENE:-assets/hub/build/qa/mesh_hygiene/mesh_hygiene.csv}"  # mesh_hygiene.py on hub_dressed_lit.blend
if [ -n "$INVIEW" ]; then
  gate=$(py -X utf8 assets/hub/qa_gate.py "$FL" --scenario "$S" --collisions "$CL" --hygiene "$HY" --in-view "$INVIEW" --cams "$CAMS"); rc=$?
else
  gate=$(py -X utf8 assets/hub/qa_gate.py "$FL" --scenario "$S" --collisions "$CL" --hygiene "$HY"); rc=$?
fi
echo "$gate" | tail -1
if [ $rc -ne 0 ]; then echo "STOP: $S fails the gate (rc $rc: $FL, $CL)"; exit 4; fi
for c in ${CAMS//,/ }; do
  free=$(df -BG /c | awk 'NR==2 {gsub("G","",$4); print $4}')
  if [ "$free" -lt 15 ]; then echo "STOP: C: has ${free} GB free (< 15 GB) before $S/$c"; exit 3; fi
  if [ -f "$OUT/$c.mp4" ]; then echo "skip $S/$c (done)"; continue; fi
  echo "== $S $c $(date +%T) (free ${free} GB)"
  n=$(py -X utf8 -c "import json;print(int(round(json.load(open('assets/hub/build/truth/scenario$( [ "$S" = S0 ] && echo _S0 || echo _$S ).json'))['seconds']*10)))")
  "$B" -b --factory-startup "$BLEND" -P assets/hub/render_cctv.py -- --cams "$c" --frames "1-$n" --out "$FR" \
    --res "$RES" --samples "$SAMPLES" --raytrace 0 --shadow-scale 0.5 --exposure 0.2 2>&1 | grep -E "^CCTV|Error"
  uv run --project backend python assets/hub/cctv_batch.py "$FR/$c" "$OUT/$c.mp4" --cam "$c" --codec h265 --width 0 \
    && rm -rf "${FR:?}/$c"
done
echo "== $S done $(date +%T)"
