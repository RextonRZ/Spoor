#!/usr/bin/env bash
# QUEUE B2: one full-settings still per camera (frame 150 of S0), CCTV pass with this camera's OSD clock / lens.
#   bash assets/hub/b2_stills.sh [frame]
set -u
cd "$(dirname "$0")/../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
F="${1:-150}"
RAW=assets/hub/build/qa/b2_raw
OUT=assets/hub/build/qa/b2
mkdir -p "$RAW" "$OUT"
CAMS=$(py -X utf8 -c "print(','.join(f'CAM_{k:02d}' for k in range(1, 19)))")
"$B" -b --factory-startup assets/hub/build/hub_S0.blend -P assets/hub/render_cctv.py -- --cams "$CAMS" \
  --frames "$F-$F" --out "$RAW" --res 2688x1520 --samples 2 --raytrace 0 --shadow-scale 0.5 --exposure 0.2 2>&1 | grep -E "^CCTV|Error"
for c in ${CAMS//,/ }; do
  d=$(mktemp -d)
  cp "$RAW/$c/$(printf %04d "$F").png" "$d/0001.png"
  uv run --project backend python assets/hub/cctv_batch.py "$d" "$OUT/${c}_tmp.mp4" --cam "$c" --codec h264 --width 0 \
    --first "$F" >/dev/null
  ffmpeg -y -loglevel error -i "$OUT/${c}_tmp.mp4" -frames:v 1 "$OUT/${c}.png" && rm -f "$OUT/${c}_tmp.mp4"
  rm -rf "$d"
done
py -X utf8 - <<'PY'
from PIL import Image
from pathlib import Path
out = Path("assets/hub/build/qa/b2")
ims = [Image.open(out / f"CAM_{k:02d}.png").resize((672, 380)) for k in range(1, 19)]
sheet = Image.new("RGB", (672 * 3, 380 * 6))
for i, im in enumerate(ims):
    sheet.paste(im, ((i % 3) * 672, (i // 3) * 380))
sheet.save(out / "contact_sheet.jpg", quality=88)
print("sheet ok")
PY
