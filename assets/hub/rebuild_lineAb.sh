#!/usr/bin/env bash
# rebuild.sh for the line A (b) spec variant (M5): spec -> hub_lineAb.blend -> dressed_base -> dressed_lit.
#   bash assets/hub/rebuild_lineAb.sh [--from dress|relight]
set -eu
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
FROM=build
EXPOSURE=0.2  # the batch setting (rebuild.sh)
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
  step make_lineab_spec
  py -X utf8 $H/mocap/make_lineab_spec.py
  step build_hub
  "$B" -b --factory-startup -P $H/build_hub.py -- --spec $H/hub_spec_lineAb.json --out $H/build/hub_lineAb.blend
fi
if [ "$FROM" = build ] || [ "$FROM" = dress ]; then
  step dress_hub
  "$B" -b --factory-startup $H/build/hub_lineAb.blend -P $H/dress_hub.py -- --spec hub_spec_lineAb.json \
    --save $H/build/hub_lineAb_dressed_base.blend
fi
step relight
"$B" -b --factory-startup $H/build/hub_lineAb_dressed_base.blend -P $H/light_test.py -- --cams "" --out $H/build/qa/_light \
  --spots 0.8 --floor-mul 0.35 --floor-rough 0.7 --floor-spec 0.12 --exposure "$EXPOSURE" \
  --save $H/build/hub_lineAb_dressed_lit.blend
step done
