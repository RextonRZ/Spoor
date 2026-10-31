"""hub_spec_lineAb.json = an exact copy of the canonical hub_spec.json (builder note 1040, 31 Oct).

Since 31 Oct the canonical spec IS line A layout (b): build_hub_plan.py writes hub_spec.json with LINE_A_LAYOUT = "b"
(the collector turning east at the feed line y 12.25, D02's stub belt, "line_a": {"layout": "b"}). This script only
keeps the old file name working for the commands that pass --spec hub_spec_lineAb.json (flow, dress_hub,
rebuild_lineAb.sh); it refuses to copy a spec that is not layout b. The frontend seeds from hub_spec.json.

  py -X utf8 assets/hub/mocap/make_lineab_spec.py   -> assets/hub/hub_spec_lineAb.json (gitignored copy)
"""
import json
from pathlib import Path

HUB = Path(__file__).resolve().parents[1]
src = (HUB / "hub_spec.json").read_text(encoding="utf-8")
s = json.loads(src)
assert s.get("line_a", {}).get("layout") == "b", "hub_spec.json is not layout b: run build_hub_plan.py (LINE_A_LAYOUT)"
assert any(c["id"] == "d02_stub" for c in s["machines"]["conveyors"])
out = HUB / "hub_spec_lineAb.json"
out.write_text(src, encoding="utf-8")
print("wrote", out, "(copy of hub_spec.json)")
