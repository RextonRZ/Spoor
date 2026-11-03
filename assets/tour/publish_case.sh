#!/usr/bin/env bash
# Publish a case's 3D renders to the web app (run from the repo root):
#   tour  - the fly-through (tour_render.py -> assets/tour/out3): tour.mp4 (a key frame every 10 for seeking) + tour.json
#   spin  - the turntables (spin_render.py --carton -> assets/tour/spin_c): smaller WebP frames + spin.json
#   truth - the ground-truth clip (truth_render.py -> assets/tour/truth): truth.mp4 at 20 fps (the simulation's 10 fps,
#           twice as fast) + truth.json
#   bash assets/tour/publish_case.sh <case_id> tour|spin|truth
set -euo pipefail
case_id=$1; what=$2
dst=frontend/public/tour/$case_id
case $what in
  tour)
    ffmpeg -v error -y -framerate 30 -i assets/tour/out3/frames/f%05d.jpg -c:v libx264 -crf 22 -preset slow -g 10 -pix_fmt yuv420p \
      -movflags +faststart "$dst/tour.mp4"
    cp assets/tour/out3/tour.json "$dst/tour.json" ;;
  spin)
    python assets/tour/publish_spin.py assets/tour/spin_c "$dst/spin" ;;
  truth)
    ffmpeg -v error -y -framerate 20 -i assets/tour/truth/frames/f%05d.jpg -c:v libx264 -crf 22 -preset slow -g 20 -pix_fmt yuv420p \
      -movflags +faststart "$dst/truth.mp4"
    cp assets/tour/truth/truth.json "$dst/truth.json" ;;
esac
ls -la "$dst" | grep -E "tour|truth|spin"
