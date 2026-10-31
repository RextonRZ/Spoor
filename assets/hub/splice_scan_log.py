"""A longer scan log around a scenario's window (builder notes 0445 / 0755: ~25 min of hub traffic around S2, so the
stalled-parcel inbox can show "the hub kept working and this parcel didn't turn up"), sim-only, label scan_simulated:

  blender ... flow.py -- --scenario S2 --seconds 90 --preroll 1400 --sim-only <x.json> --scan-extend 300
  python assets/hub/splice_scan_log.py --scenario S2 --ext <x>_scan_ext.jsonl

- The window [0, its length]: the full scenario run's own log, unchanged (the story and every station's scans).
- Before and after it: the sim-only run's sorter traffic (the same hub, seed and clock domains; a longer pre-roll so it
  starts before the story parcel's divert). That run is its own simulation, so its parcels get synthetic CTX ids (never
  an id of the full run), its copy of the story is dropped, and so is every parcel of it that has a line inside the
  window (cut there, its sequence would read as stalled).
- Bagging downstream of the sorter, outside the window: each chute's bag_drop events fill a bag (24-32 parcels); a full
  bag is closed (SP-BAG-<chute>), scanned into a roll cage (SP-CAGE-E / -W by chute side) and a new bag opened; a cage
  that holds 6 bags is loaded at an outbound door 3-8 min later (its RFID tag read at SP-RFID-D07..D12). The window
  keeps its own station scans only.
- Per parcel, the bagger scans it into the bag open at its chute (container_add at SP-BAG-<chute>, the spec's bagging
  scan) 20 s-4 min after the divert and before that bag closes (before the window only: the window keeps its own
  station scans).
- The log ends with the window (the sim run's traffic after it is not used: its parcels are not the full run's). Without it every parcel's last scan was its divert, and the inbox
  called the early C07 / C10 ones stalled once a later bag close showed the chute kept working (builder note 1140).
- Check: the inbox's stalled rule (backend forensics/exceptions.py: allowance per last scan, and the next point on the
  route kept scanning other parcels) run on the spliced log; only parcels the scenario truth designs as stalled
  ("designed_stalled") may appear, else exit 3.
Clock domains as flow.py (handheld offset + batch upload). Writes build/sim/events_scan_simulated_<S>_long.jsonl and
prints a report (span, counts per kind, the subject's lines, traffic after its last scan). Reads truth files (QA only:
the Spoor runtime never reads them).
"""
import argparse
import collections
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

HUB = Path(__file__).resolve().parent
BUILD = HUB / "build"
ap = argparse.ArgumentParser()
ap.add_argument("--scenario", default="S2")
ap.add_argument("--ext", required=True)
ap.add_argument("--seed", type=int, default=7)
a = ap.parse_args()
S = a.scenario
main_rows = [json.loads(l) for l in (BUILD / "sim" / f"events_scan_simulated_{S}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
true_rows = [json.loads(l) for l in (BUILD / "truth" / f"events_truth_{S}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
assert len(main_rows) == len(true_rows), "the truth log is written line for line with the scan log"
sc = json.loads((BUILD / "truth" / f"scenario_{S}.json").read_text(encoding="utf-8"))
rt = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))
spec = json.loads((HUB / "hub_spec_lineAb.json").read_text(encoding="utf-8"))
t0 = datetime.fromisoformat(sc["t0"])
W = float(sc["seconds"])
HH, WCS = rt["handheld_fleet"], rt["wcs"]
rnd = random.Random(a.seed * 1009 + 17)
used = {r.get("parcel_id") for r in main_rows} | {r.get("container_id") for r in main_rows} \
    | {r.get("bag_id") for r in main_rows} | {r.get("item_id") for r in main_rows}
syn = {}


def synth_id(k):
    if k not in syn:
        r = random.Random(f"{S}-long-parcel-{k}")
        while True:
            pid = "CTX" + "".join(str(r.randint(0, 9)) for _ in range(12))
            if pid not in used:
                used.add(pid)
                syn[k] = pid
                break
    return syn[k]


def new_id(prefix, digits):
    while True:
        x = prefix + "".join(str(rnd.randint(0, 9)) for _ in range(digits))
        if x not in used:
            used.add(x)
            return x


def domain(sp):
    return "clkd_handheld" if (sp or "").startswith(("SP-BAG", "SP-CAGE", "SP-IN-", "SP-REWORK", "SP-OVERSIZE", "SP-LOAD",
                                                     "SP-STORE")) else "clkd_wcs"


USERS = {"SP-IN-N": "OP-***17", "SP-IN-S": "OP-***31", "SP-BAG": "OP-***08", "SP-CAGE": "OP-***08",
         "SP-LOAD": "OP-***52", "SP-REWORK": "OP-***44", "SP-STORE": "OP-***44", "SP-OVERSIZE": "OP-***61"}  # (flow.py)


def stamp(e, t):
    """flow.py's clock domains: the device time (with its offset), and a handheld's batch upload."""
    dom = domain(e.get("scan_point"))
    off = (HH if dom == "clkd_handheld" else WCS).get("clock_offset_s", 0.0)
    e["time"] = (t0 + timedelta(seconds=t + off)).isoformat(timespec="milliseconds")
    e["clock_domain"] = dom
    if dom == "clkd_handheld":
        sp_ = e.get("scan_point") or ""
        e.setdefault("scanner_user", next((v for k_, v in USERS.items() if sp_.startswith(k_)), "OP-***00"))
        e["received_time"] = (t0 + timedelta(seconds=t + off + 60 * HH.get("batch_upload_delay_min", 0)
                                             + rnd.uniform(5, 90))).isoformat(timespec="seconds")
    return e


out = []  # (true t, row)
for r, tr in zip(main_rows, true_rows):
    out.append((float(tr["true_t_s"]), dict(r)))
ext = [json.loads(l) for l in Path(a.ext).read_text(encoding="utf-8").splitlines() if l.strip()]
drops = []  # (t, chute) for the bagging model, outside the window
rejects = []  # reject-bin drops outside the window (rework -> some held in the exception store)
divs = []  # (t, chute, parcel id): the bagger's per-parcel scans
n_ext = 0
# a sim parcel with any line inside the window is left out whole: cut at the window its sequence would just stop (and
# read as stalled in the inbox), or start mid-route after it
cut = {e.get("parcel_k") for e in ext if 0 <= float(e["t_s"]) <= W and e.get("parcel_k") is not None}
for e in ext:
    t = float(e["t_s"])
    if 0 <= t <= W or e.get("story") or e.get("parcel_k") in cut:
        continue  # the window and the story: the full run's own lines
    if t < -1e9:
        continue
    k = e.pop("parcel_k", None)
    for key in ("t_s", "time", "story", "label"):
        e.pop(key, None)
    e["parcel_id"] = synth_id(k) if k is not None else None
    if e["event"] == "tunnel_read":
        e["barcode"] = e["parcel_id"]
    out.append((t, dict(label="scan_simulated", **stamp(e, t))))
    if e["event"] == "reject_bin":
        rejects.append(t)
    n_ext += 1
    if e["event"] == "bag_drop" and e.get("chute"):
        drops.append((t, e["chute"]))
    if e["event"] == "divert_confirm" and e.get("parcel_id") and e.get("chute") not in (None, "REJECT"):
        divs.append((t, e["chute"], e["parcel_id"]))

# bagging model (outside the window): bags fill from the drops, full bags go into cages, full cages are loaded
side = {c["id"]: ("SP-CAGE-W" if c["x"] < 40.0 else "SP-CAGE-E") for c in spec["machines"]["chutes"]}
doors = ["D07", "D08", "D09", "D10", "D11", "D12"]
fill = collections.Counter()
cap = {}
bag = {}
cage = {}  # side -> (cage id, bags in it)
hist = collections.defaultdict(list)  # chute -> [(opened t, bag id, closed t)]
n_bag = 0
for t, ch in sorted(drops):
    cap.setdefault(ch, rnd.randint(24, 32))
    if ch not in bag:
        bag[ch] = new_id(f"BAG-{ch}-", 4)
        hist[ch].append([-1e9, bag[ch], 1e9])
    fill[ch] += 1
    if fill[ch] < cap[ch]:
        continue
    tc = t + rnd.uniform(20, 60)  # the bagger closes it, scans it into a cage, hangs a new bag
    if 0 <= tc <= W + 120:
        fill[ch] = cap[ch] - 1  # (not inside the window: it keeps its own station scans; try with the next drop)
        continue
    sp = side.get(ch, "SP-CAGE-E")
    cid, nb = cage.get(sp, (None, 0))
    if cid is None:
        cid, nb = new_id("RC-", 3), 0
    for dt, row in ((0.0, dict(event="bag_close", scan_point=f"SP-BAG-{ch}", chute=ch, bag_id=bag[ch])),
                    (rnd.uniform(10, 30), dict(event="container_add", scan_point=sp, container_id=cid, item_id=bag[ch],
                                               item_kind="bag")),
                    (rnd.uniform(35, 50), dict(event="bag_open", scan_point=f"SP-BAG-{ch}", chute=ch,
                                               bag_id=(nb_id := new_id(f"BAG-{ch}-", 4))))):
        out.append((tc + dt, dict(label="scan_simulated", **stamp(dict(row, parcel_id=None), tc + dt))))
        n_bag += 1
    hist[ch][-1][2] = tc
    hist[ch].append([tc + dt, nb_id, 1e9])  # (dt: the last of the three steps, the new bag's open scan)
    bag[ch], fill[ch], cap[ch] = nb_id, 0, rnd.randint(24, 32)
    nb += 1
    if nb >= 6:  # a full cage goes out on a truck: its tag is read at the door's portal
        tl = tc + rnd.uniform(180, 480)
        if not (0 <= tl <= W):
            out.append((tl, dict(label="scan_simulated", **stamp(dict(event="rfid_read", scan_point=f"SP-RFID-{rnd.choice(doors)}",
                                                                      container_id=cid, rssi_dbm=round(rnd.uniform(-58, -51), 1),
                                                                      parcel_id=None), tl))))
            n_bag += 1
        cid, nb = None, 0
    cage[sp] = (cid, nb)

rb = random.Random(a.seed * 31 + 5)  # (its own stream: the bagging model's ids and times stay as they were)
n_bagscan = 0
for t, ch, pid in divs:
    hs = hist.get(ch) or [[-1e9, new_id(f"BAG-{ch}-", 4), 1e9]]
    hist[ch] = hs
    b_ = next((h for h in hs if h[0] <= t <= h[2]), None) or next(h for h in hs if h[0] >= t)  # (between close and
    ts = t + rb.uniform(20, 240)  # open: the next bag)
    ts = min(ts, b_[2] - 3.0) if b_[2] - 3.0 > t + 5 else t + 5
    if ts >= 0:  # in the window (keeps its own station scans) or after the log: under 20 min old at the end, in
        continue  # progress for the inbox (a divert needing its bag scan by the end was 20 min before it)
    out.append((ts, dict(label="scan_simulated", **stamp(dict(event="container_add", scan_point=f"SP-BAG-{ch}",
                                                              container_id=b_[1], item_kind="parcel", parcel_id=pid,
                                                              device="handheld"), ts))))
    n_bagscan += 1

# exception store scan-in (SP-STORE-IN, the handheld at Z11's doorway): a no-read in the reject bin is keyed by hand at
# rework (its label read there) and about half are held in the exception store, scanned in at its door 2-6 min later.
# Only before the window: CAM_19 films that door in it, and nobody carries a parcel in there then but the S2 actor
# (who does not scan it: the story parcel never gets this line)
n_store = 0
for i_, tr_ in enumerate(rejects):
    if rnd.random() < 0.5:
        continue
    t_rw = tr_ + rnd.uniform(60, 150)
    t_in = t_rw + rnd.uniform(120, 360)
    if t_in >= -5.0:
        continue
    pid_ = synth_id(("rework", i_))
    out.append((t_rw, dict(label="scan_simulated", **stamp(dict(event="manual_encoded", scan_point="SP-REWORK",
                                                                 parcel_id=pid_, note="waybill keyed at rework (tunnel no-read)"), t_rw))))
    out.append((t_in, dict(label="scan_simulated", **stamp(dict(event="store_scan_in", scan_point="SP-STORE-IN",
                                                                 container_id="LOC-Z11-EXCEPTION", item_kind="parcel",
                                                                 parcel_id=pid_), t_in))))
    n_store += 1

# the log ends with the window: after it only the sim run's (different) parcels carried on, so the full run's parcels
# still on the line at the window's end looked lost while "the hub kept working" (5 tunnel reads in its last 5 s)
t_cut = W
n_cut_end = sum(1 for t, _ in out if t > t_cut)
out = [(t, r) for t, r in out if t <= t_cut]
out.sort(key=lambda tr_: tr_[0])
rows = [r for _, r in out]

# the inbox's stalled rule on this log (backend forensics/exceptions.py)
ALLOW = {"tunnel_read": 30.0, "induct_to_carrier": 105.0, "recirculate_chute_full": 105.0, "divert_confirm": 1200.0,
         "container_add": 7200.0, "bag_close": 7200.0}
NEXT = {"tunnel_read": {"induct_to_carrier"}, "induct_to_carrier": {"divert_confirm", "recirculate_chute_full"},
        "recirculate_chute_full": {"divert_confirm", "recirculate_chute_full"},
        "divert_confirm": {"container_add", "bag_close", "bag_open"}, "container_add": {"rfid_read"},
        "bag_close": {"rfid_read"}}
t_end = out[-1][0]
last_ = {}
for t, r in out:
    if r.get("parcel_id"):
        last_[r["parcel_id"]] = (t, r)
stalled = []
for pid, (t, r) in last_.items():
    ev_ = r["event"]
    if ev_ in ("rfid_read",) or ev_ not in ALLOW or t_end - t <= ALLOW[ev_]:
        continue
    sp_ = r.get("scan_point") or ""
    at = ("SP-BAG-" + sp_.removeprefix("SP-DIV-")) if sp_.startswith("SP-DIV-") else         (sp_.replace("SP-TUNNEL", "SP-INDUCT") if sp_.startswith("SP-TUNNEL") else None)
    if any(t + ALLOW[ev_] < t2 and r2["event"] in NEXT.get(ev_, ()) and (at is None or r2.get("scan_point") == at)
           and r2.get("parcel_id") != pid for t2, r2 in out):
        stalled.append(dict(parcel_id=pid, last=ev_, scan_point=sp_, at=r["time"]))
designed = set(sc.get("designed_stalled", []))
outp = BUILD / "sim" / f"events_scan_simulated_{S}_long.jsonl"
outp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
sid = sc.get("story_parcel") or sc.get("story_container")
subj = [(t, r) for t, r in out if sid and (r.get("parcel_id") == sid or r.get("container_id") == sid)]
t_last = max(t for t, _ in subj) if subj else None
after = [(t, r) for t, r in out if t_last is not None and t > t_last and r.get("parcel_id") != sid]
kinds_after = collections.Counter(r["event"] for _, r in after)
rep = dict(out=str(outp.relative_to(HUB.parent.parent)).replace("\\", "/"), rows=len(rows), from_full_run=len(main_rows),
           sim_parcels_cut_by_window=len(cut),
           sorter_rows_outside_window=n_ext, bagging_model_rows=n_bag, bagger_parcel_scans=n_bagscan, rows_after_sorter_end_dropped=n_cut_end,
           synthetic_ids=len(syn), store_scan_ins=n_store,
           stalled_like_inbox=dict(n=len(stalled), designed=sorted(designed),
                                   not_designed=[x for x in stalled if x["parcel_id"] not in designed][:20]),
           span_true=[(t0 + timedelta(seconds=out[0][0])).isoformat(), (t0 + timedelta(seconds=out[-1][0])).isoformat()],
           subject=sid, subject_events=[(r["event"], r.get("scan_point"), r["time"]) for _, r in subj],
           after_subject_last_scan=dict(minutes=round((out[-1][0] - t_last) / 60, 1) if t_last is not None else None,
                                        by_kind=dict(kinds_after)),
           per_kind=dict(collections.Counter(r["event"] for r in rows)))
print(json.dumps(rep, indent=1))
if any(x["parcel_id"] not in designed for x in stalled):
    print("CHECK FAILED: the inbox would call", sum(x["parcel_id"] not in designed for x in stalled),
          "parcels stalled that the scenario does not design as stalled")
    raise SystemExit(3)
print("CHECK OK: stalled like the inbox", len(stalled), "(designed", len(designed), ")")
