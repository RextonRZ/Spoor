#!/usr/bin/env bash
# One flow timeline per scenario, from the same lit hub (rebuild.sh --from relight makes build/hub_dressed_lit.blend):
#   bash assets/hub/run_scenarios.sh [S0 S2 ...]
# Each run writes build/hub_<S>.blend + build/sim/events_scan_simulated[_<S>].jsonl + build/truth/{flow_truth,
# events_truth,scenario}_<S>.* (S0 keeps the default file names). Scenario lengths / render cameras: SCEN_CFG below
# (render_plan from hub_spec, plus cameras the raycast check showed see the story: CAM_01 / CAM_06 for S2, the
# chute cameras for S5).
set -u
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
declare -A SECONDS_OF=([S0]=30 [S1]=90 [S2]=90 [S3]=30 [S4]=30 [S5]=60)
LIST="${*:-S0 S1 S2 S3 S4 S5}"
mkdir -p assets/hub/build/qa/scenarios
for S in $LIST; do
  echo "== $S $(date +%T)"
  "$B" -b --factory-startup assets/hub/build/hub_dressed_lit.blend -P assets/hub/flow.py -- --scenario "$S" \
    --seconds "${SECONDS_OF[$S]}" --save "assets/hub/build/hub_$S.blend" > "assets/hub/build/qa/scenarios/flow_$S.log" 2>&1
  echo "   exit $? $(grep -c Traceback assets/hub/build/qa/scenarios/flow_$S.log) tracebacks"
done
echo "== done $(date +%T)"
