#!/usr/bin/env bash
# S2 proof on CAM_19 (review 021 #3): the final look (EEVEE, batch settings) -> the CCTV pass (cctv_look: lens, sensor,
# ISP, H.265, OSD) -> native-pixel crops of the doorway region, going in (carrying) and coming out (empty-handed).
#   bash assets/hub/mocap/s2_cctv_proof.sh <blend> <out dir> "<frames in>" "<frames out>"
set -eu
cd "$(dirname "$0")/../../.."
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
BLEND="$1"; OUT="$2"; FIN="$3"; FOUT="$4"
mkdir -p "$OUT/raw" "$OUT/cctv"
for f in $FIN $FOUT; do
  "$B" -b --factory-startup "$BLEND" -P assets/hub/render_cctv.py -- --cams CAM_19 --frames "$f-$f" --out "$OUT/raw" \
    --res 2688x1520 --samples 2 --raytrace 0 --shadow-scale 0.5 --exposure 0.2 2>&1 | grep -E "^CCTV|Error" || true
done
K1=$(py -X utf8 -c "import json;print(json.load(open('assets/hub/render_truth.json'))['cameras']['CAM_19']['lens_k1'])")
for p in "$OUT"/raw/CAM_19/*.png; do
  n=$(basename "$p" .png)
  uv run --project backend python assets/hub/cctv_look.py "$p" "$OUT/cctv/$n.png" --cam CAM_19 --label "EXCEPTION STORE" --k1 "$K1"
done
py -X utf8 - "$OUT" "$FIN" "$FOUT" <<'PY'
import sys
from pathlib import Path
from PIL import Image, ImageDraw
out, fin, fout = Path(sys.argv[1]), sys.argv[2].split(), sys.argv[3].split()
box = (1000, 250, 2300, 1250)  # the doorway and the approach from the cages (CAM_19, 2688 x 1520)
for tag, fs in (("in", fin), ("out", fout)):
    ims = []
    for f in fs:
        p = next((q for q in (out / "cctv").glob(f"*{int(f):04d}*.png")), None) or next(
            (q for q in (out / "cctv").glob(f"*{f}*.png")), None)
        if p is None:
            continue
        im = Image.open(p).convert("RGB").crop(box)
        ImageDraw.Draw(im).text((8, 8), f"f{f} {tag}", fill=(255, 255, 0))
        ims.append(im)
    if ims:
        w, h = ims[0].size
        sheet = Image.new("RGB", (w * min(3, len(ims)), h * ((len(ims) + 2) // 3)))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % 3) * w, (i // 3) * h))
        sheet.save(out / f"crops_{tag}.png")
        print("wrote", out / f"crops_{tag}.png", len(ims))
PY
