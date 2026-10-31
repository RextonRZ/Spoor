"""Pre-render gate (reviews 006 / 009): read a scenario's QA flags (qa_checks.py on its .blend) and fail on the hard
gates, so a batch never renders a build with them.

  py -X utf8 assets/hub/qa_gate.py <auto_flags.csv> [--scenario S2] [--collisions <collisions.csv>]
  exit 0 = pass, 1 = fail, 2 = STRICT fail. render_batch.sh renders only on 0: nothing is overridden (owner rule,
  Rexton 30 Oct 09:38: zero interpenetration, residual acceptance withdrawn, no GATE_FORCE)

Gates: any high body_in_cage / held_clip_head / accessory_off_head / accessory_fit row; any parcel overlap >= 5 cm for
>= 3 frames; any row of collision_check.py (>= 1 cm interpenetration, any frame, any pair) = STRICT.
STRICT (review 009): a failing row that involves the scenario's story object, or that lies within +-10 s of one of the
scenario's key events AND within 3 m of the story parcel at that moment (or is a scenario-only worker). Reads
build/truth/ - this is builder QA, never the Spoor runtime.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent
HARD = ("body_in_cage", "held_clip_head", "accessory_off_head", "accessory_fit", "accessory_face")
FPS, F0, WINDOW_S, NEAR_M = 10, 1, 10.0, 3.0


def story(scen):
    """(story object name, key frames, {frame: (x, y)} of the story parcel) from the scenario's truth files."""
    suf = "" if scen == "S0" else f"_{scen}"
    tr = json.loads((HUB / "build" / "truth" / f"scenario{suf or '_S0'}.json").read_text(encoding="utf-8"))
    obj = tr.get("story_object")
    keys = [v for k, v in tr.items() if k.endswith("_t_s") and isinstance(v, (int, float))]
    pid = tr.get("story_parcel")
    ev = HUB / "build" / "truth" / f"events_truth{suf}.jsonl"
    if pid and ev.exists():
        for line in ev.read_text(encoding="utf-8").splitlines():
            r = json.loads(line) if line.strip() else {}
            if r.get("parcel_id") == pid and isinstance(r.get("true_t_s"), (int, float)):
                keys.append(r["true_t_s"])
    track = {}
    ft = HUB / "build" / "truth" / f"flow_truth{suf}.json"
    if obj and ft.exists():
        for p in json.loads(ft.read_text(encoding="utf-8")).get("parcels", []):
            if p.get("object") == obj:
                track = {int(f): (xyz[0], xyz[1]) for f, xyz in p.get("track", {}).items()}
    return obj, [F0 + round(t * FPS) for t in keys], track


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flags", nargs="?", default=str(HUB / "build" / "qa" / "auto_flags.csv"))
    ap.add_argument("--scenario")
    ap.add_argument("--collisions", help="collision_check.py collisions.csv (required by render_batch.sh)")
    ap.add_argument("--hygiene", help="mesh_hygiene.py mesh_hygiene.csv: any same-facing z-fighting face fails")
    # owner (Rexton 08:16 Sat, per 021c_review): the S2 render gate is 0 collision rows VISIBLE in any camera S2
    # renders. With --in-view (mocap/rows_in_view.py's json on the same collisions.csv) and --cams (the cameras this
    # batch renders), only rows those cameras see count; rows nobody films are fixed before a scenario that films them
    ap.add_argument("--in-view", help="rows_in_view.py json for --collisions (owner S2 rule: visible rows only)")
    ap.add_argument("--cams", help="comma list of the cameras being rendered (with --in-view)")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.flags, encoding="utf-8")))
    fails = [r for r in rows if r["check"] in HARD and r["severity"] == "high"]
    for r in rows:
        if r["check"] != "parcel_overlap":
            continue
        m = re.search(r"overlap by (\d+) cm", r["detail"])
        if m and int(m.group(1)) >= 5 and int(r["frame_end"]) - int(r["frame_start"]) + 1 >= 3:
            fails.append(r)
    obj, key_frames, track = story(a.scenario) if a.scenario else (None, [], {})
    strict = []
    for r in fails:
        f0, f1 = int(r["frame_start"]), int(r["frame_end"])
        hit = bool(obj) and obj in r["detail"]
        near_event = any(f0 - WINDOW_S * FPS <= k <= f1 + WINDOW_S * FPS for k in key_frames)
        if not hit and near_event:
            if re.match(r"worker_s\d", r["worker_name"]):
                hit = True
            m = re.search(r"at \(([-\d.]+), ([-\d.]+)\)", r["detail"])
            if m and track:
                x, y = float(m.group(1)), float(m.group(2))
                for f in range(f0, f1 + 1):
                    g = min(track, key=lambda q: abs(q - f))
                    if ((track[g][0] - x) ** 2 + (track[g][1] - y) ** 2) ** 0.5 <= NEAR_M:
                        hit = True
                        break
        if hit:
            strict.append(r)
    coll = []
    if a.collisions:
        cp = Path(a.collisions)
        if not cp.exists():
            print(f"GATE STRICT FAIL: no collision report {cp} (run collision_check.py on the scenario blend)")
            return 2
        coll = list(csv.DictReader(open(cp, encoding="utf-8")))
        if a.in_view:
            iv = json.loads(Path(a.in_view).read_text(encoding="utf-8"))
            if iv.get("rows") != len(coll):
                print(f"GATE STRICT FAIL: {a.in_view} was made from another collision report ({iv.get('rows')} rows, "
                      f"{cp} has {len(coll)})")
                return 2
            want = set((a.cams or "").split(",")) - {""}
            if not want:
                print("GATE STRICT FAIL: --in-view needs --cams (the cameras being rendered)")
                return 2
            n_all = len(coll)
            coll = [r for r in iv.get("seen_rows", []) if want & set(r.get("cams", []))]
            print(f"GATE in-view: {len(coll)} of {n_all} collision rows are seen by {sorted(want)} (owner S2 rule)")
        for r in coll[:20]:
            print(f"STRICT collision f{r['frame']} {r['a']} | {r['b']} {r['depth_cm']} cm {r.get('bone', '')}")
    if a.hygiene:  # review mesh_hygiene: z-fighting must be 0
        hp = Path(a.hygiene)
        hy = list(csv.DictReader(open(hp, encoding="utf-8"))) if hp.exists() else []
        zf = [r for r in hy if int(r.get("zfight_faces") or 0) > 0]
        for r in zf[:10]:
            print(f"GATE mesh_hygiene {r['object']}: {r['zfight_faces']} z-fighting faces ({r.get('zfight_with', '')})")
        fails += [dict(check="mesh_hygiene", severity="high", worker_name=r["object"], frame_start="1", frame_end="1",
                       detail=f"{r['zfight_faces']} z-fighting faces") for r in zf]
        if not hp.exists():
            print(f"GATE mesh_hygiene: no report {hp}")
    for r in fails:
        tag = "STRICT" if r in strict else "GATE"
        print(f"{tag} {r['worker_name']} f{r['frame_start']}-{r['frame_end']} {r['check']}: {r['detail']}")
    n_hard = sum(r["check"] in HARD for r in fails)
    verdict = "STRICT FAIL" if strict or coll else ("FAIL" if fails else "PASS")
    print(f"GATE {verdict}: {n_hard} hard, {len(fails) - n_hard} parcel overlaps >= 5 cm x 3 frames, "
          f"{len(strict)} strict (story object {obj or '-'}, {len(key_frames)} key events), "
          f"{len(coll) if a.collisions else 'unchecked'} collision frame-hits")
    return 2 if strict or coll else (1 if fails else 0)


if __name__ == "__main__":
    sys.exit(main())
