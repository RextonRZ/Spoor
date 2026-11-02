"""One-off import correction (2 Nov): the hub importer typed every parcel-into-container scan as a cage, including a
parcel into its chute's bag (container BAG-...). seed_nokey.py now types them by the export's id scheme; for a store
seeded before that, this appends an incorrect_data correction per affected scan (the log is append-only: originals
stay, the correction stands in their place for every reader).

    uv run --project ../backend python scripts/correct_bag_types.py --data .local/backend-data-s2r18c [--go]
"""
import argparse
from pathlib import Path

from spoor.contracts import ScanEvent, new_id
from spoor.contracts.parcels import ContainerType
from spoor.store import EvidenceStore

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--go", action="store_true")
a = ap.parse_args()
store = EvidenceStore.sqlite_file(Path(a.data) / "spoor.db")
scans = store.find(ScanEvent)
done = {s.corrects_scan_event_id for s in scans if s.corrects_scan_event_id}
todo = [s for s in scans if s.event_kind.value == "container_add" and s.container and s.container.value.startswith("BAG-")
        and s.container_type and s.container_type.value == "cage" and s.corrects_scan_event_id is None
        and s.scan_event_id not in done]
print(len(todo), "parcel-into-bag scans typed as cage")
if a.go:
    for s in todo:
        store.put(s.model_copy(update={"scan_event_id": new_id("scan_event"), "container_type": ContainerType.BAG,
                                       "corrects_scan_event_id": s.scan_event_id, "correction_reason": "incorrect_data"}))
    print("corrected", len(todo))
