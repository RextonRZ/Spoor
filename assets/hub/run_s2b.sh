#!/usr/bin/env bash
# One S2 hub run to the RENDER blend (gate-zero loop, Rexton 31 Oct): window blend + sim-only long log (parallel),
# splice (+ stalled check), scan-route check, still-parcel settle, scan-checkpoint patch, then every gate on all 19
# cameras on that final blend + the checkpoints' own gate (no worker through them, which cameras see them).
#   bash assets/hub/run_s2b.sh <tag> [--from settle]
# Final blend: assets/hub/build/hub_lineAb_S2_<tag>c.blend. Reports: qa/review/s2_hub_<tag>/ (gates/, scanchk/).
set -u
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
TAG="$1"
FROM="${3:-flow}"
[ "${2:-}" = "--from" ] || FROM=flow
UNSTAFF="opener,dock_D02,lineB"  # 021d / 021d2 reviews (S2 card limitations)
O="qa/review/s2_hub_$TAG"
BL="assets/hub/build/hub_lineAb_S2_$TAG.blend"
BC="assets/hub/build/hub_lineAb_S2_${TAG}c.blend"
mkdir -p "$O"
t() { echo "== $1 $(date +%T)"; }
if [ "$FROM" = flow ]; then
  t "flow (window) + sim-only long log (parallel)"
  "$B" -b --factory-startup assets/hub/build/hub_lineAb_dressed_lit.blend -P assets/hub/flow.py -- \
    --spec hub_spec_lineAb.json --scenario S2 --seconds 90 --unstaff "$UNSTAFF" --save "$BL" > "$O/flow.log" 2>&1 &
  P1=$!
  "$B" -b --factory-startup assets/hub/build/hub_lineAb_dressed_lit.blend -P assets/hub/flow.py -- \
    --spec hub_spec_lineAb.json --scenario S2 --seconds 90 --preroll 1400 --unstaff "$UNSTAFF" \
    --sim-only "$O/sim_long.json" --scan-extend 300 > "$O/sim_long.log" 2>&1 &
  P2=$!
  wait $P1; wait $P2
  grep -E "^SNAP|Traceback|Error" "$O/flow.log" | cut -c1-300 | head -5
  if [ ! -f "$BL" ]; then echo "STOP: no $BL"; exit 2; fi
  t "splice"
  py -X utf8 assets/hub/splice_scan_log.py --scenario S2 --ext "$O/sim_long_scan_ext.jsonl" > "$O/splice.json"
  echo "splice rc $?"
  t "scan routes"
  py -X utf8 assets/hub/check_scan_routes.py > "$O/routes.txt" 2>&1
  grep S2 "$O/routes.txt"
fi
t "settle still parcels + scan checkpoints (screens from this run's tunnel camera)"
"$B" -b --factory-startup "$BL" -P assets/hub/settle_overlaps.py -- --save "$BC" 2>&1 | grep -E "^SETTLE|Error" | cut -c1-200
"$B" -b --factory-startup "$BC" -P assets/hub/scanner_photos.py -- --tile 2>&1 | grep -E "^TILE|Error"
py -X utf8 assets/hub/make_dws_screen.py
"$B" -b --factory-startup "$BC" -P assets/hub/scan_checkpoints.py -- --save "$BC" 2>&1 | grep -E "^PATCH|Error" | cut -c1-80
rm -f assets/hub/build/*.blend1
t "gates (all cameras) on the render blend"
bash assets/hub/gate_all.sh "$BC" "$O/gates" S2 900
t "checkpoint gate"
"$B" -b --factory-startup "$BC" -P assets/hub/scan_checkpoints.py -- --check --out "$O/scanchk" 2>&1 | grep -E "^CHECK \{" | cut -c1-400
t "done"
