"""SIMULATED 30-day history for the Hub insights demo (Rexton 2 Nov: a demo feed for the trends, for the video's close).

Never evidence and never mixed into a case: it lives only in this view, every number labelled "simulated". It is not
typed in: a seeded generator, calibrated on the one real shift in the store (each place's volume, the tunnel's read
rate, each hop's time, the cases' outcomes), draws 29 earlier days around those rates with day-to-day noise and a weekly
pattern, plus a few NAMED scenario events (listed in the output) so the trends have something to show. TODAY is the real
shift, scaled to a day only where a per-day volume is shown (the scale is stated). Same seed, same history.
"""

import math
import random
from datetime import datetime, timedelta

SEED = 20261028
DAYS = 30
SHIFT_HOURS = 16.0  # the hub's working day the real shift is scaled to (stated on the screen)
EVENTS = [  # (first day, last day, place group, what, read-rate factor or None, extra cases at the place)
    (11, 13, "Scan tunnel", "Tunnel camera dirty: more labels not read until it was cleaned", 0.955, 0),
    (20, 20, "Exception store", "Store-door scanner offline for a shift: parcels went in unscanned", None, 3),
    (24, 25, "Dock gates", "Dock D07 RFID reads whole cages as loaded (reader moved)", None, 2),
]
BREAKS = [  # where a lost parcel's trail breaks (the case mix), each with the fix the screen shows
    ("Reject chute", "Unread at the tunnel, not matched to its unload scan", 0.34),
    ("Exception store", "Carried in, not scanned in", 0.22),
    ("Chutes", "Diverted to the wrong chute", 0.18),
    ("Dock gates", "Cage marked loaded with the parcel still inside", 0.14),
    ("Cages", "Taken out of its cage, no scan", 0.12),
]


def _poisson(rnd: random.Random, lam: float) -> int:
    l_, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= l_:
            return k
        k += 1


def demo_history(today: dict, *, end: datetime) -> dict:
    """`today` = the real insights (scorecard, flow, loop, cost). Returns the simulated days and the real today."""
    rnd = random.Random(SEED)
    sc = today.get("scorecard") or {"rows": []}
    minutes = max(1, sc.get("minutes", 1))
    scale = SHIFT_HOURS * 60 / minutes  # the real shift's per-minute volume, over a working day
    tunnel = next((r for r in sc["rows"] if r["group"] == "Scan tunnel"), None)
    real_rate = tunnel["read_rate"] if tunnel and tunnel["read_rate"] else 0.99
    base_rate = min(0.995, real_rate + 0.028)  # the usual: today's rate is the dip (today is shown as measured)
    groups: dict[str, dict] = {}
    for r in sc["rows"]:
        g = groups.setdefault(r["group"], {"through": 0, "read_rate": r["read_rate"]})
        g["through"] += r["reads"] + r["no_reads"]
    days = []
    for d in range(DAYS - 1):
        day = (end - timedelta(days=DAYS - 1 - d)).date()
        week = 0.86 if day.weekday() >= 5 else 1.0  # quieter weekends
        vol = week * rnd.uniform(0.9, 1.08)
        ev = [e for e in EVENTS if e[0] <= d + 1 <= e[1]]
        rate = base_rate * next((e[4] for e in ev if e[4]), 1.0) + rnd.gauss(0, 0.002)
        parcels = round(groups.get("Unload", {"through": 450})["through"] * scale * vol)
        lam = 1.1 * vol + 4 * (1 - rate) * 10 + sum(e[5] for e in ev)
        cases = []
        for _ in range(_poisson(rnd, lam)):
            r_ = rnd.random()
            where = next((b for b in BREAKS if (r_ := r_ - b[2]) < 0), BREAKS[-1])
            for e in ev:
                if e[5] and rnd.random() < 0.6:
                    where = next(b for b in BREAKS if b[0] == e[2])
            answered = rnd.random() < 0.95
            checked = answered and rnd.random() < 0.82
            confirmed = checked and rnd.random() < 0.88
            replanned = checked and not confirmed
            found_after = replanned and rnd.random() < 0.6
            cases.append({"where": where[0], "what": where[1], "answered": answered, "checked": checked, "confirmed": confirmed,
                          "replanned": replanned, "found_after_replan": found_after,
                          "answer_s": round(math.exp(rnd.gauss(math.log(270), 0.35))) if answered else None,
                          "usd": round(rnd.uniform(0.9, 1.9), 2) if answered else 0.0})  # fmt: skip
        days.append({"date": day.isoformat(), "simulated": True, "parcels": parcels, "tunnel_read_rate": round(min(0.999, rate), 4),
                     "cases": cases, "events": [e[3] for e in ev]})  # fmt: skip
    loop = today["loop"]
    days.append({"date": end.date().isoformat(), "simulated": False, "parcels": None, "parcels_in_shift": groups.get("Unload", {}).get("through"),
                 "tunnel_read_rate": real_rate, "events": [], "cases": [
                     {"where": b["where"], "what": b["what"], "answered": True, "checked": False, "confirmed": False, "replanned": False,
                      "found_after_replan": False, "answer_s": None, "usd": None} for b in today["breaks"] for _ in b["cases"]],
                 "cases_opened": len(loop["opened"])})  # fmt: skip

    def tot(key):
        return sum(sum(1 for c in d["cases"] if c[key]) for d in days[:-1])

    sim_cases = [c for d in days[:-1] for c in d["cases"]]
    where: dict[tuple, int] = {}
    for c in sim_cases:
        where[(c["where"], c["what"])] = where.get((c["where"], c["what"]), 0) + 1
    ans = sorted(c["answer_s"] for c in sim_cases if c["answer_s"])
    return {
        "label": "Simulated demo history: 29 days drawn by a seeded generator calibrated on today's real shift; today is real",
        "scale": {"shift_minutes": minutes, "day_hours": SHIFT_HOURS},
        "events": [{"days": f"{a}-{b}" if a != b else str(a), "group": g, "what": w} for a, b, g, w, _, _ in EVENTS],
        "days": days,
        "totals": {"cases": len(sim_cases), "answered": tot("answered"), "checked": tot("checked"), "confirmed": tot("confirmed"),
                   "replanned": tot("replanned"), "found_after_replan": tot("found_after_replan"),
                   "median_answer_s": ans[len(ans) // 2] if ans else None, "usd": round(sum(c["usd"] for c in sim_cases), 2),
                   "usual_read_rate": round(base_rate, 4), "today_read_rate": real_rate},
        "where": [{"where": k[0], "what": k[1], "cases": v} for k, v in sorted(where.items(), key=lambda kv: -kv[1])],
    }  # fmt: skip
