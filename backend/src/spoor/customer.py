"""The update to the customer who asked (the "Customer asked" flow, meta_stack_and_complaint section 2).

A courier's customer service sends the hub a trace request; the hub never talks to the customer. When the case has an
answer, Spoor drafts the short update customer service can pass on. It is written ONLY from verified facts (where the
verifier placed the parcel, or its last scan record, and what floor staff recorded when they found it), never from the
agents' ideas; it names no person, blames no one, and says nothing about intent. A person approves it; in this demo
"send" only marks it sent (an audit entry with the approver and the time): Spoor sends nothing.

Two stages: before the parcel is found on the floor, a holding update (where it most likely is, a team member is
checking); after, the found update (found at the hub, being sent on; no delivery date is promised: none is in the facts).
Each fact carries a reference to its evidence (the moment and camera, or the floor record), shown under the draft.

The model (Muse Spark Open on Baseten) only words the facts, in English or Malay, short or detailed, for a marketplace
chat or an email; a draft that trips the safety terms, or a case with no model, gets the plain template instead."""

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from spoor.agents.orchestrator import latest_answer
from spoor.contracts import Case
from spoor.reasoning import BackendError, JsonBackend
from spoor.safety import find_forbidden
from spoor.store import AgentStep, EvidenceStore

SYSTEM = """You write a short update for a courier's customer service to pass on to a customer whose parcel is late.
Use ONLY the facts given. Plain words, friendly and calm. Say where the parcel is and what the hub is doing next. Never
name or describe a person, never blame anyone, never suggest theft or intent, never add a time, place, date or promise
that is not in the facts. No dashes. Do not mention cameras' names or record ids."""
STYLE = {
    ("chat", "short"): "A marketplace chat reply: two or three short sentences, no greeting line, no sign-off.",
    ("chat", "detailed"): "A marketplace chat reply: four short sentences, no sign-off.",
    ("email", "short"): ("An email. greeting: one short line, like 'Dear customer,'. paragraphs: two short paragraphs of one or two "
                         "sentences: where the parcel is (and what changed in its tracking, if a fact says so), then what happens "
                         "next. No sign-off: it is added."),
    ("email", "detailed"): ("An email. greeting: one short line, like 'Dear customer,'. paragraphs: three short paragraphs of one to "
                            "three sentences: where the parcel is, what changed in its tracking (if a fact says so), what happens next. "
                            "No sign-off: it is added."),
}
# an email is laid out by Spoor, not the model (Rexton 3 Nov: one run-on paragraph is not an email): the model writes a
# greeting and paragraphs; the subject and sign-off are fixed words
SIGN = {"en": "Kind regards,\nCustomer Service\nCONTOH Express", "ms": "Yang benar,\nKhidmat Pelanggan\nCONTOH Express"}
SUBJECT = {("en", "holding"): "Update on your parcel {wb}", ("ms", "holding"): "Kemas kini bungkusan anda {wb}",
           ("en", "found"): "Your parcel {wb} has been found", ("ms", "found"): "Bungkusan anda {wb} telah ditemui"}
LANG = {"en": "Write in English.", "ms": "Write in Bahasa Melayu (Malaysian Malay), natural and polite."}


class CustomerUpdate(BaseModel):
    message: str = Field(max_length=900)


class EmailUpdate(BaseModel):
    greeting: str = Field(max_length=80)
    paragraphs: list[str] = Field(min_length=1, max_length=3)


def email(greeting: str, paragraphs: list[str], lang: str) -> str:
    return "\n\n".join([greeting.strip(), *(p.strip() for p in paragraphs if p.strip()), SIGN.get(lang, SIGN["en"])])


def _found(store: EvidenceStore, case_id: str):
    from spoor.contracts import SearchOutcome

    outs = [o for o in store.find(SearchOutcome, case_id=case_id) if o.outcome == "found"]
    return max(outs, key=lambda o: o.recorded_at) if outs else None


def facts_for(case: Case, answer: dict | None, tz: str = "Asia/Kuala_Lumpur", *, found=None, lang: str = "en",
              ) -> tuple[list[str], list[dict | None]] | None:  # fmt: skip
    """The verified facts in plain words, each with its evidence reference (None: no verified answer to tell)."""
    zone = ZoneInfo(tz)
    waybill = case.target_description.split(" ")[-1]
    ms = lang == "ms"
    if found is not None:
        at = found.recorded_at.astimezone(zone)
        return ([f"{'Nombor penjejakan' if ms else 'Tracking number'} {waybill}.",
                 (f"Pasukan hab menemui bungkusan ini di hab pengisihan pada {at:%d %b} jam {at:%H:%M}." if ms else
                  f"Hub staff found it at the sorting hub on {at:%d %b} at {at:%H:%M}."),
                 ("Ia sedang dihantar semula; tarikh penghantaran baharu akan dimaklumkan sebaik sahaja ditempah." if ms else
                  "It is being sent on; the new delivery date follows as soon as it is booked.")],
                [None, {"kind": "floor", "at": found.recorded_at.isoformat(), "label": f"Found by floor staff {at:%H:%M}"}, None])
    if not answer:
        return None
    for o in answer.get("objects", []):
        if (f := o.get("inside")) is not None:
            at = datetime.fromisoformat(f["iso"]["carried_in_at"]).astimezone(zone)
            place = f["place"].split(" (")[0].lower()
            ref = {"kind": "camera", "at": f["iso"]["carried_in_at"], "label": f"Carried in {at:%H:%M} (store door camera)"}
            if ms:
                return ([f"Nombor penjejakan {waybill}.",
                         f"Ia berada di hab pengisihan: pada {at:%d %b} jam {at:%H:%M} ia dibawa masuk ke {place} hab, dan belum keluar sejak itu.",
                         "Kemas kini penjejakan sebelum ini menyatakan ia dimuatkan ke trak; kemas kini itu salah.",
                         "Seorang ahli pasukan hab sedang memeriksa tempat itu supaya ia dapat dihantar."],
                        [None, ref, {"kind": "record", "label": "Truck record checked against the cameras"}, None])
            return ([f"Tracking number {waybill}.",
                     (f"It is at the sorting hub: on {at:%d %b} at {at:%H:%M} it was moved into the hub's {place}, "
                      "and it has not left it since."),
                     "An earlier tracking update said it was loaded onto a truck; that update was wrong.",
                     "A hub team member is checking that spot so it can be sent on."],
                    [None, ref, {"kind": "record", "label": "Truck record checked against the cameras"}, None])
        if (s := o.get("last_scan")) is not None and s.get("located_by") == "camera":
            at = datetime.fromisoformat(s["at"]).astimezone(zone)
            ref = {"kind": "camera", "at": s["at"], "label": f"Last scan {at:%H:%M}, seen on camera"}
            if ms:
                return ([f"Nombor penjejakan {waybill}.",
                         f"Imbasan terakhirnya di hab pengisihan ialah pada {at:%d %b} jam {at:%H:%M}, dan kamera hab mengesahkan ia berada di situ.",
                         "Seorang ahli pasukan hab sedang memeriksa tempat itu supaya ia dapat dihantar."], [None, ref, None])
            return ([f"Tracking number {waybill}.",
                     (f"Its last scan at the sorting hub was on {at:%d %b} at {at:%H:%M}, and the hub's cameras confirm "
                      "it was there at that moment."), "A hub team member is checking that spot so it can be sent on."],
                    [None, ref, None])
    return None


def template(facts: list[str], lang: str = "en", channel: str = "chat") -> str:
    hello = "Terima kasih atas kesabaran anda." if lang == "ms" else "Hello, thank you for your patience."
    bye = ("Kami akan memaklumkan anda sebaik sahaja ia dalam perjalanan." if lang == "ms"
           else "We will let you know as soon as it is on its way.")
    if channel == "email":
        thanks = "Terima kasih atas kesabaran anda." if lang == "ms" else "Thank you for your patience."
        return email("Pelanggan yang dihormati," if lang == "ms" else "Dear customer,",
                     [f"{thanks} {facts[1]}", " ".join(facts[2:]), bye], lang)
    return " ".join([hello, *facts[1:], bye])


def draft(store: EvidenceStore, case: Case, backend: JsonBackend | None, *, now: datetime, channel: str = "chat",
          language: str = "en", tone: str = "short") -> dict:  # fmt: skip
    """Draft the update from verified facts; stored as an AgentStep (role customer_update), not sent."""
    found = _found(store, case.case_id)
    got = facts_for(case, latest_answer(store, case.case_id), found=found, lang=language)
    if got is None:
        return {"status": "no_answer", "note": "no verified answer yet: nothing to tell the customer"}
    facts, refs = got
    text, model, why = template(facts, language, channel), "template", ""
    if backend is not None:
        try:
            system = f"{SYSTEM}\n{STYLE.get((channel, tone), STYLE[('chat', 'short')])}\n{LANG.get(language, LANG['en'])}"
            if channel == "email":
                reply = backend.complete(system=system, content="\n".join(facts), output=EmailUpdate, name="customer_update")
                words = email(reply.data.greeting, reply.data.paragraphs, language)
            else:
                reply = backend.complete(system=system, content="\n".join(facts), output=CustomerUpdate, name="customer_update")
                words = reply.data.message
            words = words.replace(chr(0x2014), ",").replace(chr(0x2013), ",").strip()
            if hits := find_forbidden(words):
                why = f"model draft used {sorted({t for _, t in hits})}: plain template used"
            else:
                text, model = words, backend.model
        except BackendError as e:
            why = f"model unavailable ({str(e)[:80]}): plain template used"
    n = len([s for s in store.find(AgentStep, case_id=case.case_id) if s.role == "customer_update"])
    content = {"draft": text, "facts": facts, "refs": refs, "model": model, "note": why, "approved": False, "sent": False,
               "stage": "found" if found else "holding", "channel": channel, "language": language, "tone": tone,
               "subject": (SUBJECT[(language if language in ("en", "ms") else "en", "found" if found else "holding")]
                           .format(wb=case.target_description.split(" ")[-1]) if channel == "email" else None),
               "label": "draft for customer service to pass on; a person approves it; Spoor sends nothing"}
    store.put(AgentStep(step_id=f"custupd_{case.case_id}_{n + 1:02d}", case_id=case.case_id,
                        request_id=f"custupd_{case.case_id}", seq=n + 1, role="customer_update", kind="final",
                        content=content, at=now))  # fmt: skip
    return {"status": "drafted", **content}


def approve(store: EvidenceStore, case: Case, *, text: str, approver: str, now: datetime) -> dict:
    """A person approves the (possibly edited) latest draft and marks it sent to customer service. In this demo nothing
    leaves Spoor: the record (text, approver, time, content hash) is what customer service would receive."""
    steps = [s for s in store.find(AgentStep, case_id=case.case_id) if s.role == "customer_update"]
    if not steps:
        raise ValueError("no draft to approve")
    last = max(steps, key=lambda s: s.at).content
    if find_forbidden(text):
        raise ValueError("the edited text uses words Spoor never sends to a customer")
    content = {**last, "draft": text.strip(), "approved": True, "sent": True, "approved_by": approver,
               "sent_at": now.isoformat(), "edited": text.strip() != last.get("draft", "").strip(),
               "label": "approved by a person and marked sent to customer service (demo: no message leaves Spoor)"}
    content["content_sha256"] = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    store.put(AgentStep(step_id=f"custupd_{case.case_id}_{len(steps) + 1:02d}", case_id=case.case_id,
                        request_id=f"custupd_{case.case_id}", seq=len(steps) + 1, role="customer_update", kind="final",
                        content=content, at=now))  # fmt: skip
    return {"status": "sent", **content}
