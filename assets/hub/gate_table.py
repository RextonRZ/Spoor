"""The gate table in plain words for one hub run (gate-zero loop, Rexton 31 Oct): every gate's count, what it means,
and where the rest come from. The S2 actor's turn rate (22-24 deg/frame) is exempt (Rexton).

  py -X utf8 assets/hub/gate_table.py qa/review/s2_hub_<tag> [--prev qa/review/s2_hub_<prev tag>]
"""
import argparse
import collections
import csv
import json
import re
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("run")
ap.add_argument("--prev", default="")
ap.add_argument("--pairs", action="store_true")  # + per collision pair, before / after (touch-ups: none may get worse)
a = ap.parse_args()
EXEMPT_TURN = {"worker_s2_1"}


def counts(run):
    g = Path(run) / "gates"
    mg = json.loads((g / "motion_gates" / "motion_gates.json").read_text(encoding="utf-8"))
    iv = json.loads((g / "rows_in_view.json").read_text(encoding="utf-8"))
    flags = list(csv.DictReader(open(g / "checks" / "auto_flags.csv", encoding="utf-8")))
    hy = list(csv.DictReader(open(g / "mesh_hygiene" / "mesh_hygiene.csv", encoding="utf-8")))
    hard = [r for r in flags if r["check"] in ("body_in_cage", "held_clip_head", "accessory_off_head", "accessory_fit",
                                                "accessory_face") and r["severity"] == "high"]
    ovl = [r for r in flags if r["check"] == "parcel_overlap" and (m := re.search(r"overlap by (\d+) cm", r["detail"]))
           and int(m.group(1)) >= 5 and int(r["frame_end"]) - int(r["frame_start"]) + 1 >= 3]
    turns = [r for r in mg["turns_over_max"] if r["worker"] not in EXEMPT_TURN]
    piles = mg["piles"]
    c = collections.OrderedDict()
    c["head clips / body in cage (hard)"] = (len(hard), [f"{r['worker_name']} f{r['frame_start']}" for r in hard[:3]])
    c["parcels overlapping >= 5 cm"] = (len(ovl), [r["detail"][:60] for r in ovl[:3]])
    c["held objects jumping / slipping"] = (len(mg["held_jumps"]), [f"{k} x{n}" for k, n in collections.Counter(
        r["obj"] for r in mg["held_jumps"]).most_common(4)])
    c["parcels floating / stacked wrong"] = (len(piles), [f"{k} x{n}" for k, n in collections.Counter(
        r["obj"] for r in piles).most_common(4)])
    c["collisions seen by any of the 19 cameras"] = (iv["seen"], [f"{k} x{n}" for k, n in iv["by_pair"][:4]])
    c["turns over 22 deg/frame (S2 actor exempt)"] = (len(turns), [f"{k} x{n}" for k, n in collections.Counter(
        r["worker"] for r in turns).most_common(3)])
    c["parcels moving faster than the belts"] = (len(mg["conveyed_over_speed"]), [f"{k} x{n}" for k, n in collections.Counter(
        r["obj"] for r in mg["conveyed_over_speed"]).most_common(3)])
    c["workers lying on the floor"] = (sum(e["lying"] for e in mg["pelvis_by_worker"].values()), [])
    c["z-fighting faces"] = (sum(int(r.get("zfight_faces") or 0) for r in hy), [r["object"] for r in hy if int(r.get("zfight_faces") or 0)][:3])
    sp = Path(run) / "scanchk" / "scan_checkpoints.json"
    if sp.exists():
        s = json.loads(sp.read_text(encoding="utf-8"))
        c["scan checkpoints hit by anything"] = (s["hits_n"], [f"{h['a']}|{h['b']}" for h in s["hits"][:3]])
    return c


cur = counts(a.run)
prev = counts(a.prev) if a.prev else {}
w = max(len(k) for k in cur)
print(f"{'gate':<{w}}  {'now':>5}  {'before':>6}  where the rest come from")
for k, (n, why) in cur.items():
    pv = prev.get(k, ("",))[0]
    print(f"{k:<{w}}  {n:>5}  {pv!s:>6}  {', '.join(why)}")
print("ALL ZERO" if all(n == 0 for n, _ in cur.values()) else f"NOT ZERO: {sum(1 for n, _ in cur.values() if n)} gates")


def pairs(run):
    iv = json.loads((Path(run) / "gates" / "rows_in_view.json").read_text(encoding="utf-8"))
    return collections.Counter(f"{r['a'].split('_body')[0]} | {r['b'].split('_body')[0]}" for r in iv["seen_rows"])


if a.pairs and a.prev:
    now_, was_ = pairs(a.run), pairs(a.prev)
    worse = [k for k in now_ if now_[k] > was_.get(k, 0)]
    print()
    print(f"{'collision pair (seen by any camera)':<60} {'now':>5} {'before':>6}")
    for k in sorted(set(now_) | set(was_), key=lambda k_: -max(now_.get(k_, 0), was_.get(k_, 0))):
        print(f"{k:<60} {now_.get(k, 0):>5} {was_.get(k, 0):>6}{'  WORSE' if k in worse else ''}")
    print("NO PAIR WORSE" if not worse else f"WORSE: {len(worse)} pairs")
