#!/usr/bin/env bash
# The whole hub, from the spec to the animated scene (one timeline: footage, scan_simulated log, truth).
#   bash assets/hub/rebuild.sh [--from dress|relight|flow] [--exposure 0.1]
# build_hub (geometry) -> dress_hub (materials, props, cameras) -> light_test --save (LED rows, white walls,
# mid-grey semi-matte floor; review 001 #1) -> flow (parcels, station workers, events, truth).
set -eu
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
FROM=build
EXPOSURE=0.2  # batch settings (no ray tracing, shadow 0.5, 2 spp; look_stats 30 Oct): walls 171-175, floor 96-99, 0.04 % > 230
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --exposure) EXPOSURE="$2"; shift 2 ;;
    *) echo "unknown arg $1"; exit 2 ;;
  esac
done
H=assets/hub
step() { echo "== $1 $(date +%T)"; }
if [ "$FROM" = build ]; then
  step build_hub
  "$B" -b --factory-startup -P $H/build_hub.py -- --spec $H/hub_spec.json --out $H/build/hub.blend
fi
if [ "$FROM" = build ] || [ "$FROM" = dress ]; then
  step dress_hub
  "$B" -b --factory-startup $H/build/hub.blend -P $H/dress_hub.py -- --save $H/build/hub_dressed_base.blend
fi
if [ "$FROM" != flow ]; then
  step relight
  "$B" -b --factory-startup $H/build/hub_dressed_base.blend -P $H/light_test.py -- --cams "" --out $H/build/qa/_light \
    --spots 0.8 --floor-mul 0.35 --floor-rough 0.7 --floor-spec 0.12 --exposure "$EXPOSURE" \
    --save $H/build/hub_dressed_lit.blend
fi
step flow
"$B" -b --factory-startup $H/build/hub_dressed_lit.blend -P $H/flow.py -- --save $H/build/hub_dressed.blend
step done
