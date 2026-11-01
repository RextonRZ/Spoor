"""Scenario cards (QUEUE D4) from the render-side scenario truth (evaluator material).

  py -X utf8 assets/hub/make_cards.py [S0 S1 ...]

Writes, per scenario, ml/evaluation/scenarios/<S>/:
  case_input.json     what an investigator is ASKED (the parcel / cage id, the time window, the cameras, the scan-log
                      file): no answer in it - the frontend seeds its input cases from this file only (QUEUE F1)
  scenario_card.md    one page: what happens, which cameras, which scan lines, the expected Spoor answer (incl.
                      unknown / no coverage). EVALUATOR-ONLY: the Spoor runtime never reads it.
"""
import json
from datetime import datetime, timedelta
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent
ROOT = HUB.parent.parent
BUILD = HUB / "build"
OUT = ROOT / "ml" / "evaluation" / "scenarios"
TITLES = {"S0": "Control path", "S1": "No-read rework", "S2": "Removal into the blind spot",
          "S3": "Phantom containment", "S4": "Mis-load onto the wrong truck (RFID cross-read)", "S5": "Look-alike pair"}
# S0 (control): every camera except CAM_17, the yard (no S0 story passes there; saves 1/18 of the batch: B2 pre-review
# #6). S4 keeps it: the mis-load happens at the lorries
CAMS = {"S0": [f"CAM_{k:02d}" for k in range(1, 20) if k != 17],
        "S1": ["CAM_01", "CAM_04", "CAM_05", "CAM_06", "CAM_07", "CAM_08", "CAM_09", "CAM_10", "CAM_11", "CAM_12"],
        "S2": ["CAM_01", "CAM_06", "CAM_09", "CAM_11", "CAM_13", "CAM_15", "CAM_19"],
        "S3": ["CAM_09", "CAM_10", "CAM_11", "CAM_13", "CAM_14", "CAM_15", "CAM_16"],
        "S4": ["CAM_10", "CAM_11", "CAM_13", "CAM_14", "CAM_15", "CAM_16", "CAM_17"],
        "S5": ["CAM_01", "CAM_04", "CAM_05", "CAM_06", "CAM_07", "CAM_09", "CAM_10", "CAM_11"]}


def main(scens):
    manifest = []
    for S in scens:
        suf = "" if S == "S0" else f"_{S}"
        tp = BUILD / "truth" / f"scenario{suf or '_S0'}.json"
        if not tp.exists():
            print(f"{S}: no scenario truth ({tp.name}) - run run_scenarios.sh first")
            continue
        tr = json.loads(tp.read_text(encoding="utf-8"))
        log = BUILD / "sim" / f"events_scan_simulated{suf}.jsonl"
        rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
        sid = tr.get("story_parcel") or tr.get("story_container")
        lines = [r for r in rows if sid and (r.get("parcel_id") == sid or r.get("container_id") == sid
                                             or r.get("item_id") == sid)]
        if S == "S3" and tr.get("bag_id"):
            lines += [r for r in rows if r.get("container_id") == tr["bag_id"] and r not in lines]
        d = OUT / S
        d.mkdir(parents=True, exist_ok=True)
        ask = {"scenario": S, "title": TITLES.get(S, S), "synthetic": True, "subject_id": sid,
               "subject_kind": "container" if tr.get("story_container") else "parcel",
               "question": (f"Where is {sid} now, and when was it last seen?" if S != "S4"
                            else f"Which truck did roll cage {sid} go onto?"),
               # the complaint is a legitimate input (review 007 Q1): the waybill comes from the customer, not the card
               "waybill": sid if not tr.get("story_container") else None,
               "complaint": (f"Customer reports parcel {sid} never arrived." if not tr.get("story_container") else
                             f"The receiving depot says roll cage {sid} did not arrive on its truck."),
               "window": {"start": tr.get("t0"), "seconds": tr.get("seconds")},
               "cameras": CAMS.get(S, []), "scan_log": str(log.relative_to(ROOT)).replace("\\", "/"),
               "clips": [f"assets/hub/build/renders/{S}/{c}.mp4" for c in CAMS.get(S, [])]}
        (d / "case_input.json").write_text(json.dumps(ask, indent=1), encoding="utf-8")
        md = [f"# {S} · {TITLES.get(S, S)}", "",
              "> EVALUATOR-ONLY. Synthetic scenario from the CONTOH Express hub (fictional). The Spoor runtime never "
              "reads this card or anything under `assets/hub/build/truth/`.", "",
              f"**Length:** {tr.get('seconds')} s at 10 fps from {tr.get('t0')} (hub clock; each camera's OSD runs "
              "on its own drifting clock).", "",
              f"**Subject:** `{sid}`", "", f"**What happens:** {tr.get('what', '-')}", "",
              f"**Cameras rendered:** {', '.join(CAMS.get(S, []))}", "",
              "**Scan lines about the subject** (scan_simulated, device clocks):", ""]
        md += [f"- `{r['time']}` {r['event']} @ {r.get('scan_point', '-')} ({r.get('clock_domain')})" for r in lines] \
            or ["- none (no scanner saw it in or before the window)"]
        md += ["", f"**Expected Spoor answer:** {tr.get('expected_answer', '-')}", ""]
        if tr.get("expected_one_liner"):  # scenarios_v2 pass 2: the sharp line + what must not be said (scored)
            md += [f"**One line:** {tr['expected_one_liner']}", ""]
        if tr.get("must_not"):
            md += ["**Must not:**", ""] + [f"- {m}" for m in tr["must_not"]] + [""]
        if tr.get("limitations"):
            md += ["**Known limitations of the coverage:**", ""] + [f"- {m}" for m in tr["limitations"]] + [""]
        md += ["**Key truth values:**", "", "```json", json.dumps({k: v for k, v in tr.items() if k not in (
                   "what", "expected_answer", "expected_one_liner", "must_not", "limitations")}, indent=1), "```", "",
               "Key stills: `stills/` (3 frames: before, the moment, after).", "",
               "**Hub load:** two induction lines (A: 4 inductors off the dock-fed queue; B: 3 inductors off gaylords). "
               "The sorter loop runs at about 27-32 % carrier occupancy - a believable mid-shift load (review 013: "
               "accepted; the earlier 30-35 % target was not sourced)."]
        (d / "scenario_card.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        print(f"{S}: card + case_input ({len(lines)} scan lines about {sid})")
        # what each recorder's own export says its clip starts at (its on-screen clock at frame 0): every recorder
        # runs on its own clock, so the app must fit them to the sorter's clock, never trust these (fit_camera_clocks)
        if tr.get("t0"):
            rt = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
            t0 = datetime.fromisoformat(tr["t0"])
            starts = {cam: (t0 + timedelta(seconds=c.get("clock_offset_s", 0.0))).isoformat(timespec="milliseconds")
                      for cam, c in sorted(rt.items())}
            (d / "clip_starts.json").write_text(json.dumps(starts, indent=1) + chr(10), encoding="utf-8")
        rel = lambda q: Path(*([".."] * len(OUT.relative_to(ROOT).parts)), q.relative_to(ROOT)).as_posix()
        manifest.append({"scenario": S, "title": TITLES.get(S, S), "parcel": sid,
                         "subject_kind": ask["subject_kind"],
                         "clips": rel(BUILD / "renders" / S), "scans": rel(log), "clip_start": tr.get("t0")})
    # QUEUE F1: the frontend seeds one input case per scenario from this (question inputs only, no answers)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def check(scens):
    """Every scenario's case_input subject is in its scan log with exactly the scan lines its card lists (builder note
    0515 #1: S2's case_input asked about a parcel of an older run - re-run this after every scenario run)."""
    bad = []
    for S in scens:
        d = OUT / S
        if not (d / "case_input.json").exists():
            continue
        ask = json.loads((d / "case_input.json").read_text(encoding="utf-8"))
        log = ROOT / ask["scan_log"]
        rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []
        sid = ask["subject_id"]
        have = {(r["time"], r["event"]) for r in rows if sid in (r.get("parcel_id"), r.get("container_id"), r.get("item_id"))}
        card = (d / "scenario_card.md").read_text(encoding="utf-8")
        listed = set()
        for ln in card.splitlines():
            if ln.startswith("- `") and "` " in ln:
                tm, rest = ln[3:].split("` ", 1)
                listed.add((tm, rest.split(" @ ")[0]))
        miss = listed - have
        ok = bool(have) and not miss
        print(f"CHECK {S}: subject {sid}: {len(have)} scan lines in {log.name}, card lists {len(listed)}, "
              f"missing {len(miss)} -> {'OK' if ok else 'FAIL'}")
        if not ok:
            bad.append(S)
    return bad


if __name__ == "__main__":
    if sys.argv[1:2] == ["--check"]:
        sys.exit(1 if check(sys.argv[2:] or ["S0", "S1", "S2", "S3", "S4", "S5"]) else 0)
    main(sys.argv[1:] or ["S0", "S1", "S2", "S3", "S4", "S5"])
    check(sys.argv[1:] or ["S0", "S1", "S2", "S3", "S4", "S5"])
