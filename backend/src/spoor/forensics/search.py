"""Floor search read model (QUEUE I7 / H12): tasks, outcomes and the case status they give.

Status: "found" once any outcome says found (the place, who, when); "searching" while a task has places left;
"none" otherwise. A "located" status (computed area collapsed to one place) is not claimed here."""

from spoor.contracts import SearchOutcome, SearchTask
from spoor.store import EvidenceStore


def search_view(store: EvidenceStore, case_id: str) -> dict:
    tasks = store.find(SearchTask, case_id=case_id)
    outcomes = store.find(SearchOutcome, case_id=case_id)
    found = next((o for o in reversed(outcomes) if o.outcome == "found"), None)
    names = {pl.area_id: pl.name for t in tasks for pl in t.places}
    status = "found" if found else "searching" if tasks else "none"
    return {
        "case_id": case_id, "status": status,
        "found": None if not found else {"area_id": found.area_id, "name": names.get(found.area_id, found.area_id),
                                         "by": found.recorded_by, "at": found.recorded_at.isoformat(),
                                         "outcome_id": found.search_outcome_id, "content_sha256": found.content_sha256},
        "not_here": sorted({o.area_id for o in outcomes if o.outcome == "not_found"}),
        "tasks": [{**t.model_dump(mode="json"),
                   "outcomes": [o.model_dump(mode="json") for o in outcomes if o.search_task_id == t.search_task_id]}
                  for t in tasks],
    }  # fmt: skip


def outcomes_by_area(store: EvidenceStore, case_id: str) -> dict[str, SearchOutcome]:
    """Latest outcome per searched place."""
    out: dict[str, SearchOutcome] = {}
    for o in store.find(SearchOutcome, case_id=case_id):
        out[o.area_id] = o
    return out
