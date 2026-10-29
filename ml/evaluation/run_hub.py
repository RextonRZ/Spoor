"""Score Spoor's no-key answers on the parcel hub (QUEUE F3). Run from backend/ (uses the runtime package):

    cd backend
    uv run python ../ml/evaluation/run_hub.py --scenario control_flow \
        --out ../frontend/.local/backend-data/evaluation

Evaluator-only: this script may read assets/hub/build/truth/ (after predictions). The runtime never does.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spoor_eval.hub import REPO, run_hub

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="control_flow")
    ap.add_argument("--scans", type=Path, default=REPO / "assets/hub/build/sim/events_scan_simulated.jsonl")
    ap.add_argument("--clips", type=Path, default=REPO / "frontend/.local/clips")
    ap.add_argument("--spec", type=Path, default=REPO / "assets/hub/hub_spec.json")
    ap.add_argument("--truth", type=Path, default=REPO / "assets/hub/build/truth")
    ap.add_argument("--clip-start", default="2026-10-28T14:32:07+08:00")
    ap.add_argument("--parcels", default="", help="comma-separated waybills; default: every identified parcel")
    ap.add_argument("--clips-note", default="", help="e.g. clips come from an earlier flow run than the scan log")
    ap.add_argument("--manifest", type=Path, default=REPO / "ml/evaluation/scenarios/manifest.json",
                    help="scenario manifest (builder); S1-S5 with renders + reference data become the headline")
    ap.add_argument("--no-control", action="store_true", help="skip the control flow when scenarios are scored")
    ap.add_argument("--out", type=Path, default=REPO / "frontend/.local/backend-data/evaluation")
    a = ap.parse_args()
    res = run_hub(scans=a.scans, clips=a.clips, spec=a.spec, truth_dir=a.truth, clip_start=a.clip_start,
                  scenario=a.scenario, out_dir=a.out, parcels=[p for p in a.parcels.split(",") if p] or None, clips_note=a.clips_note,
                  manifest=a.manifest, with_control=not a.no_control)
    print("headline:", res["headline"]["source"], res["headline"]["label"])
    if res["headline"]["caveat"]:
        print("caveat:", res["headline"]["caveat"])
    for suite in res["suites"]:
        print(f"== {suite['name']} ({suite['scenario']})")
        print(json.dumps(suite["aggregate"], indent=1))
        for c in suite["cases"]:
            print(f"{c.get('scenario', '')} {c['parcel']}  last_seen={'ok ' if c['last_seen_correct'] else 'NO '} "
                  f"{c['pred_last_event']} vs {c['truth_last_event']}  {c['abstention']}")
