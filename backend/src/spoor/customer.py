"""The update to the customer who asked (the "Customer asked" flow, meta_stack_and_complaint section 2).

A courier's customer service sends the hub a trace request; the hub never talks to the customer. When the case has an
answer, Spoor drafts the short update customer service can pass on. It is written ONLY from the verified answer (where
the verifier placed the parcel, or its last scan record), never from the agents' ideas; it names no person, blames no
one, and says nothing about intent. A person approves it; Spoor sends nothing.

The model (Muse Spark Open on Baseten) only words the facts; a draft that trips the safety terms, or a case with no
model, gets the plain template instead."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from spoor.agents.orchestrator import latest_answer
from spoor.contracts import Case
from spoor.reasoning import BackendError, JsonBackend
from spoor.safety import find_forbidden
from spoor.store import AgentStep, EvidenceStore

SYSTEM = """You write a short update for a courier's customer service to pass on to a customer whose parcel is late.
Use ONLY the facts given. Three or four short sentences, plain words, friendly and calm. Say where the parcel is and
what the hub is doing next. Never name or describe a person, never blame anyone, never suggest theft or intent, never
add a time, place or promise that is not in the facts. No dashes. Do not mention cameras' names or record ids."""


class CustomerUpdate(BaseModel):
    message: str = Field(max_length=700)


def facts_for(case: Case, answer: dict | None, tz: str = "Asia/Kuala_Lumpur") -> list[str] | None:
    """The verified answer as plain facts (None when there is no verified answer to tell the customer)."""
    if not answer:
        return None
    waybill = case.target_description.split(" ")[-1]
    zone = ZoneInfo(tz)
    for o in answer.get("objects", []):
        if (f := o.get("inside")) is not None:
            at = datetime.fromisoformat(f["iso"]["carried_in_at"]).astimezone(zone)
            place = f["place"].split(" (")[0].lower()
            return [f"Tracking number {waybill}.",
                    (f"It is at the sorting hub: on {at:%d %b} at {at:%H:%M} it was moved into the hub's {place}, "
                     "and it has not left it since."),
                    "An earlier tracking update said it was loaded onto a truck; that update was wrong.",
                    "Hub staff are retrieving it from there so it can be sent on."]
        if (s := o.get("last_scan")) is not None and s.get("located_by") == "camera":
            at = datetime.fromisoformat(s["at"]).astimezone(zone)
            return [f"Tracking number {waybill}.",
                    (f"Its last scan at the sorting hub was on {at:%d %b} at {at:%H:%M}, and the hub's cameras confirm "
                     "it was there at that moment."), "Hub staff are checking that spot so it can be sent on."]
    return None


def template(facts: list[str]) -> str:
    return " ".join(["Hello, thank you for your patience.", *facts[1:],
                     "We will let you know as soon as it is on its way."])


def draft(store: EvidenceStore, case: Case, backend: JsonBackend | None, *, now: datetime) -> dict:
    """Draft the update from the latest verified answer; stored as an AgentStep (role customer_update), not sent."""
    facts = facts_for(case, latest_answer(store, case.case_id))
    if facts is None:
        return {"status": "no_answer", "note": "no verified answer yet: nothing to tell the customer"}
    text, model, why = template(facts), "template", ""
    if backend is not None:
        try:
            reply = backend.complete(system=SYSTEM, content="\n".join(facts), output=CustomerUpdate, name="customer_update")
            words = reply.data.message.replace(chr(0x2014), ",").replace(chr(0x2013), ",").strip()
            if hits := find_forbidden(words):
                why = f"model draft used {sorted({t for _, t in hits})}: plain template used"
            else:
                text, model = words, backend.model
        except BackendError as e:
            why = f"model unavailable ({str(e)[:80]}): plain template used"
    n = len([s for s in store.find(AgentStep, case_id=case.case_id) if s.role == "customer_update"])
    content = {"draft": text, "facts": facts, "model": model, "note": why, "approved": False, "sent": False,
               "label": "draft for customer service to pass on; a person approves it; Spoor sends nothing"}
    store.put(AgentStep(step_id=f"custupd_{case.case_id}_{n + 1:02d}", case_id=case.case_id,
                        request_id=f"custupd_{case.case_id}", seq=n + 1, role="customer_update", kind="final",
                        content=content, at=now))  # fmt: skip
    return {"status": "drafted", **content}
