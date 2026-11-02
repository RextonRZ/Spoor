"""One-off (2 Nov, unload fix): W1's door was re-baked with a quiet stretch around the replayed carton (stations.py
QUIET_S), so five synthetic history lines at SP-IN-N no longer match a carton set down in the video. This appends an
incorrect_data correction per line moving it to a set-down the re-baked door really made (render side: the sim's own
dock picks, on the handheld fleet's clock like the story line). The log is append-only: originals stay, the
correction stands in their place for every reader.

    uv run --project ../backend python scripts/retime_w1_door.py --data .local/backend-data-s2r18c [--go]
"""
import argparse
from datetime import datetime
from pathlib import Path

from spoor.contracts import ScanEvent, new_id
from spoor.store import EvidenceStore

# original logged time -> the re-baked door's set-down (W1 start 14:09:31.76 + the sim's t_rel - the fleet's 2.0 s)
MOVES = {"14:09:51.500": "14:09:46.460", "14:10:00.300": "14:09:43.260", "14:10:01.100": "14:10:15.960",
         "14:10:06.200": "14:10:18.960", "14:10:08.400": "14:10:23.360"}  # fmt: skip

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--go", action="store_true")
a = ap.parse_args()
store = EvidenceStore.sqlite_file(Path(a.data) / "spoor.db")
scans = store.find(ScanEvent)
done = {s.corrects_scan_event_id for s in scans if s.corrects_scan_event_id}
todo = []
for s in scans:
    local = s.device_time_utc.astimezone(datetime.fromisoformat("2026-10-28T00:00:00+08:00").tzinfo)
    key = local.strftime("%H:%M:%S.%f")[:12]
    if s.station_id == "SP-IN-N" and local.date().isoformat() == "2026-10-28" and key in MOVES \
            and s.corrects_scan_event_id is None and s.scan_event_id not in done:
        todo.append((s, datetime.fromisoformat(f"2026-10-28T{MOVES[key]}+08:00")))
for s, t in todo:
    print(s.scan_event_id, s.device_time_utc.isoformat(), "->", t.isoformat())
if a.go:
    for s, t in todo:
        store.put(s.model_copy(update={"scan_event_id": new_id("scan_event"), "device_time_utc": t,
                                       "corrects_scan_event_id": s.scan_event_id, "correction_reason": "incorrect_data"}))
    print("corrected", len(todo))
