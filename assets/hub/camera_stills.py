"""Full-size stills of all 19 cameras for the app's Cameras monitor (the zoomable viewer), from a saved S2 blend.
Same render and CCTV look as the landing posters (landing_assets.py), but 1280x720 and not shrunk, no burned-in OSD
(the page draws each camera's name and running clock). Written to <out>/CAM_xx.jpg.

  uv run --project backend python assets/hub/camera_stills.py --blend assets/hub/build/hub_lineAb_S2_r13c.blend \\
      --out frontend/public/cameras [--frame 61]

When the final S2 render exists its MP4s go next to these as <out>/CAM_xx.mp4 and are listed in <out>/feeds.json; the page
plays them in a loop and uses the still as the poster.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))
import landing_assets as LA  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--blend", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--frame", type=int, default=61)
ap.add_argument("--res", default="1280x720")
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
spec = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
spec_cams = {c["id"]: c for c in spec["cameras"]}
truth = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
cams = sorted(spec_cams)
tmp = out / "_raw"
shutil.rmtree(tmp, ignore_errors=True)
LA.render(a.blend, cams, f"{a.frame}-{a.frame}", tmp, a.res)
for c in cams:
    img = LA.look(tmp / c / f"{a.frame:04d}.png", c, a.frame, truth, spec_cams)
    cv2.imwrite(str(out / f"{c}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
shutil.rmtree(tmp, ignore_errors=True)
print("wrote", len(cams), "stills to", out)
