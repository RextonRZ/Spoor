"""Scenario check (builder note 1040): every parcel's consecutive sorter scans fit the belt routes of the CANONICAL
spec (assets/hub/hub_spec.json, line A layout b), within the clock tolerance, unless the scenario truth designs the
conflict ("designed_route_conflicts": [parcel ids]).

  py -X utf8 assets/hub/check_scan_routes.py [S1 S2 ...]      (default: every events_scan_simulated_<S>*.jsonl)

Rules (same clock domain, the WCS):
- tunnel read -> carrier load (SP-TUNNEL -> SP-INDUCT, SP-TUNNEL-B -> SP-INDUCT-B): at least the belt travel from
  the read point to where the head parcel waits for a carrier (belt speeds as flow.py: tunnel 1.5, merge 1.8,
  line B 1.5 m/s);
- carrier load -> divert / recirculation at chute X: the loop ride from the load point to X at the loop speed, plus
  whole laps (a recirculated parcel), +- TOL. flow.py tips the carrier as it reaches the chute, so there is no slack.
Exit 1 on any conflict that is not designed. Reads truth files (QA only: the Spoor runtime never reads them).
"""
import json
import math
import sys
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent
SPEC = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
assert SPEC["line_a"]["layout"] == "b", "hub_spec.json is not the rendered layout (b)"
TOL = 0.25  # s: WCS stamps are 0.1 s, the carrier passes its point within one 0.1 s step
WAIT_MARGIN = {"SP-INDUCT": 1.37, "SP-INDUCT-B": 0.83}  # flow.MERGES: the head parcel waits this far short of the loop
L = SPEC["machines"]["loop"]
R, WCX, ECX, V = L["radius"], L["west_cx"], L["east_cx"], L["speed_mps"]
L_STR, L_ARC = ECX - WCX, math.pi * R
L_LOOP = 2 * L_STR + 2 * L_ARC
CONV = {c["id"]: c for c in SPEC["machines"]["conveyors"]}
LOAD_S = {"SP-INDUCT": CONV["merge"]["path"][-1][0] - WCX,  # both merge belts join the south straight (eastbound)
          "SP-INDUCT-B": CONV["induction_B"]["path"][-1][0] - WCX}
CHUTE_S = {c["id"]: L_STR + L_ARC + (ECX - c["x"]) for c in SPEC["machines"]["chutes"]}  # north straight, westbound
SP = {s["id"]: s["position_m"] for s in SPEC["scan_points"]}


def _len(path):
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def _after(path, xy):
    """Path length from the point of `path` nearest to xy to its end."""
    best, acc, cut = None, 0.0, 0.0
    for a, b in zip(path, path[1:]):
        seg = math.dist(a, b)
        for k in range(21):
            p = (a[0] + (b[0] - a[0]) * k / 20, a[1] + (b[1] - a[1]) * k / 20)
            d = math.dist(p, xy)
            if best is None or d < best:
                best, cut = d, acc + seg * k / 20
        acc += seg
    return acc - cut


# minimum tunnel read -> carrier load: belt travel to the wait point (flow.py belt speeds)
T_MIN = {("SP-TUNNEL", "SP-INDUCT"): _after(CONV["tunnel_line"]["path"], SP["SP-TUNNEL"][:2]) / 1.5
         + (_len(CONV["merge"]["path"]) - WAIT_MARGIN["SP-INDUCT"]) / 1.8,
         ("SP-TUNNEL-B", "SP-INDUCT-B"): (_after(CONV["induction_B"]["path"], SP["SP-TUNNEL-B"][:2])
                                          - WAIT_MARGIN["SP-INDUCT-B"]) / 1.5}


def ride(load_sp, chute):
    return ((CHUTE_S[chute] - LOAD_S[load_sp]) % L_LOOP) / V


def check(path, designed):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by = {}
    for r in rows:
        if r.get("parcel_id") and r.get("clock_domain") == "clkd_wcs":
            by.setdefault(r["parcel_id"], []).append(r)
    bad, n_pairs = [], 0
    for pid, rs in by.items():
        rs.sort(key=lambda r: r["time"])
        for a, b in zip(rs, rs[1:]):
            dt = (datetime.fromisoformat(b["time"]) - datetime.fromisoformat(a["time"])).total_seconds()
            sa, sb = a.get("scan_point"), b.get("scan_point")
            why = None
            if (sa, sb) in T_MIN:
                n_pairs += 1
                if dt < T_MIN[(sa, sb)] - TOL:
                    why = f"{sa} -> {sb} in {dt:.1f} s, the belts need >= {T_MIN[(sa, sb)]:.1f} s"
            elif sa in LOAD_S and (sb or "").startswith("SP-DIV-") and b.get("chute", sb[7:]) in CHUTE_S:
                n_pairs += 1
                r0 = ride(sa, b.get("chute") or sb[7:])
                laps = max(0, round((dt - r0) / (L_LOOP / V)))
                if abs(dt - r0 - laps * L_LOOP / V) > TOL:
                    why = (f"{sa} -> {sb} in {dt:.1f} s, the loop takes {r0:.1f} s"
                           + (f" (+ {laps} lap{'s' if laps > 1 else ''} of {L_LOOP / V:.1f} s)" if laps else ""))
            if why and pid not in designed:
                bad.append(dict(parcel_id=pid, at=a["time"], why=why))
    return n_pairs, bad


def main():
    want = sys.argv[1:]
    truth = HUB / "build" / "truth"
    logs = sorted((HUB / "build" / "sim").glob("events_scan_simulated_S*.jsonl"))
    failed = False
    for lg in logs:
        sc_id = lg.stem.removeprefix("events_scan_simulated_").split("_")[0]
        if want and sc_id not in want:
            continue
        sc_f = truth / f"scenario_{sc_id}.json"
        designed = set(json.loads(sc_f.read_text(encoding="utf-8")).get("designed_route_conflicts", [])) \
            if sc_f.exists() else set()
        n, bad = check(lg, designed)
        print(f"{lg.name}: {n} timed pairs, {len(bad)} off the canonical routes" + (" -> FAIL" if bad else " -> OK"))
        for b in bad[:8]:
            print("  ", b)
        failed |= bool(bad)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
