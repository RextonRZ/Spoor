#!/usr/bin/env bash
# One S2 hub run end to end (render agent, 31 Oct): the window blend + the sim-only long scan log (in parallel, the
# same stations unstaffed), the splice (+ its stalled check), the scan-route check, then every gate on all 19 cameras.
#   bash assets/hub/run_s2.sh <run tag, e.g. r8>
# Writes assets/hub/build/hub_lineAb_S2_<tag>.blend, build/sim/events_scan_simulated_S2{,_long}.jsonl, build/truth
# (S2), qa/review/s2_hub_<tag>/ (logs, splice.json, routes.txt, gates/).
set -u
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
TAG="$1"
UNSTAFF="opener,dock_D02,lineB"  # 021d / 021d2 reviews (S2 card limitations)
O="qa/review/s2_hub_$TAG"
BL="assets/hub/build/hub_lineAb_S2_$TAG.blend"
mkdir -p "$O"
t() { echo "== $1 $(date +%T)"; }
t "flow (window) + sim-only long log (parallel)"
"$B" -b --factory-startup assets/hub/build/hub_lineAb_dressed_lit.blend -P assets/hub/flow.py -- \
  --spec hub_spec_lineAb.json --scenario S2 --seconds 90 --unstaff "$UNSTAFF" --save "$BL" > "$O/flow.log" 2>&1 &
P1=$!
"$B" -b --factory-startup assets/hub/build/hub_lineAb_dressed_lit.blend -P assets/hub/flow.py -- \
  --spec hub_spec_lineAb.json --scenario S2 --seconds 90 --preroll 1400 --unstaff "$UNSTAFF" \
  --sim-only "$O/sim_long.json" --scan-extend 300 > "$O/sim_long.log" 2>&1 &
P2=$!
wait $P1; r1=$?
wait $P2; r2=$?
echo "flow rc $r1, sim-only rc $r2"
grep -E "^SNAP|Traceback|Error" "$O/flow.log" | head -5
if [ ! -f "$BL" ]; then echo "STOP: no $BL"; exit 2; fi
t "splice"
py -X utf8 assets/hub/splice_scan_log.py --scenario S2 --ext "$O/sim_long_scan_ext.jsonl" > "$O/splice.json"
echo "splice rc $?"
tail -1 "$O/splice.json"
t "scan routes"
py -X utf8 assets/hub/check_scan_routes.py > "$O/routes.txt" 2>&1
grep S2 "$O/routes.txt"
t "gates (all cameras)"
bash assets/hub/gate_all.sh "$BL" "$O/gates" S2 900
t "done"
