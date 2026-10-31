#!/usr/bin/env bash
# Every gate on one scenario blend, every camera (Rexton 31 Oct 14:2x: gates on all 19 cameras, not only the story
# ones). Fresh qa_checks flags each time (run 6's gate read a stale 30 Oct auto_flags.csv after qa_checks crashed).
#   bash assets/hub/gate_all.sh <scenario.blend> <out dir> [S2] [last frame 900]
# Writes <out>/: checks/auto_flags.csv, collisions/, motion_gates/, mesh_hygiene/, rows_in_view.json (collisions),
# gates_in_view.json (motion-gate rows), people_in_view.json, gate.txt (qa_gate.py over all of it, all cameras).
set -u
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
BL="$1"; O="$2"; S="${3:-S2}"; F1="${4:-900}"
CAMS=$(py -X utf8 -c "import json;print(','.join(c['id'] for c in json.load(open('assets/hub/hub_spec.json'))['cameras']))")
mkdir -p "$O"
t() { echo "== $1 $(date +%T)"; }
t "collisions + qa_checks (parallel)"
"$B" -b --factory-startup "$BL" -P assets/hub/collision_check.py -- --out "$O/collisions" --frames "1-$F1" \
  > "$O/coll.log" 2>&1 &
QA_OUT="$O/checks" QA_F1="$F1" "$B" -b --factory-startup "$BL" -P assets/hub/qa_checks.py > "$O/qa_checks.log" 2>&1 &
wait
t "motion gates"
"$B" -b --factory-startup "$BL" -P assets/hub/qa_motion_gates.py -- --out "$O/motion_gates" --frames "1-$F1" \
  > "$O/gates.log" 2>&1
t "mesh hygiene"
"$B" -b --factory-startup "$BL" -P assets/hub/mesh_hygiene.py -- --out "$O/mesh_hygiene" > "$O/hygiene.log" 2>&1
t "in view ($CAMS)"
"$B" -b --factory-startup "$BL" -P assets/hub/mocap/rows_in_view.py -- --csv "$O/collisions/collisions.csv" \
  --cams "$CAMS" --out "$O/rows_in_view.json" > "$O/inview.log" 2>&1
"$B" -b --factory-startup "$BL" -P assets/hub/mocap/rows_in_view.py -- --csv "$O/motion_gates/gate_rows.csv" \
  --cams "$CAMS" --out "$O/gates_in_view.json" >> "$O/inview.log" 2>&1
"$B" -b --factory-startup "$BL" -P assets/hub/qa_people_in_view.py -- --cams "$CAMS" --out "$O/people_in_view.json" \
  > "$O/people.log" 2>&1
t "gate"
py -X utf8 assets/hub/qa_gate.py "$O/checks/auto_flags.csv" --scenario "$S" --collisions "$O/collisions/collisions.csv" \
  --hygiene "$O/mesh_hygiene/mesh_hygiene.csv" --in-view "$O/rows_in_view.json" --cams "$CAMS" > "$O/gate.txt"
echo "rc $?" >> "$O/gate.txt"
tail -2 "$O/gate.txt"
t "done"
