#!/usr/bin/env bash
# Review pack for a request: QA checks -> worker follow-cams (Workbench) -> final-look CCTV clips (EEVEE + CCTV pass).
#   bash assets/hub/review_pack.sh "CAM_01,CAM_02" "worker_dock_D05_n,worker_induct_1"
# Renders from a frozen copy of hub_dressed.blend so later builds can't change it mid-render. Resumable.
set -u
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
CAMS="${1:-CAM_01,CAM_02,CAM_04,CAM_10,CAM_13}"
WORKERS="${2:-}"
SNAP=assets/hub/build/hub_dressed_qa.blend
OUT=assets/hub/build/qa/review/cctv
FR=assets/hub/build/qa/_frames_final
mkdir -p "$OUT" "$FR"
cp assets/hub/build/hub_dressed.blend "$SNAP"
echo "== qa_checks $(date +%T)"
"$B" -b --factory-startup "$SNAP" -P assets/hub/qa_checks.py > assets/hub/build/qa/qa_checks.log 2>&1
if [ -n "$WORKERS" ]; then
  echo "== follow-cams $(date +%T)"
  sed -i 's#^BLEND = .*#BLEND = HUB / "build" / "hub_dressed_qa.blend"#' assets/hub/qa_videos.py
  py -X utf8 assets/hub/qa_videos.py --only "$WORKERS" --batch 6
fi
echo "== CCTV final look $(date +%T)"
"$B" -b --factory-startup "$SNAP" -P assets/hub/render_cctv.py -- --cams "$CAMS" --frames 1-300 --out "$FR" \
  --res 1280x720 --samples 2 2>&1 | grep -E "^CCTV|Error"
for c in ${CAMS//,/ }; do
  uv run --project backend python assets/hub/cctv_batch.py "$FR/$c" "$OUT/$c.mp4" --cam "$c" --codec h264 --width 1280 \
    && rm -rf "${FR:?}/$c"
done
echo "== done $(date +%T)"
ls -la "$OUT"
