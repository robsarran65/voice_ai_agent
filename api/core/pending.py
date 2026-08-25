# ============================================================
# Pending confirmations — orchestration layer
# ============================================================
# Calendar writes are held here between two turns: Candy proposes an event,
# the user says yes, and only then does it get created.
#
# The yes/no decision is made HERE, in plain code, not by the model. A model
# deciding whether it heard consent is a model that can talk itself into
# writing to a real calendar. Anything that isn't a recognised affirmative
# cancels the proposal.
#
# In-memory and process-local, which is correct for the single-user demo and
# explicitly NOT correct for multi-tenant use — see ROADMAP.md item 4's
# "Still open for SaaS" note. Swapping this for Redis is a change to this
# file alone.

import time
from dataclasses import dataclass

# A proposal the user never answers should not be sitting there minutes later
# waiting to be triggered by an unrelated "yeah".
TTL_SECONDS = 180

_AFFIRMATIVE = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "correct", "confirm",
    "confirmed", "right", "do it", "go ahead", "please do", "sounds good",
    "add it", "book it", "schedule it", "that's right", "thats right",
    "yes please", "go for it",
}
_NEGATIVE = {
    "no", "nope", "nah", "cancel", "stop", "don't", "dont", "never mind",
    "nevermind", "forget it", "no thanks", "scrap it",
}


@dataclass(frozen=True)
class Pending:
    kind: str          # currently only "calendar_event"
    payload: dict
    readback: str
    created_at: float


_store: dict[str, Pending] = {}


def put(session_id: str, kind: str, payload: dict, readback: str) -> None:
    _store[session_id] = Pending(kind, payload, readback, time.time())


def get(session_id: str) -> Pending | None:
    item = _store.get(session_id)
    if item is None:
        return None
    if time.time() - item.created_at > TTL_SECONDS:
        _store.pop(session_id, None)
        return None
    return item


def clear(session_id: str) -> None:
    _store.pop(session_id, None)


def _normalise(text: str) -> str:
    return "".join(c for c in (text or "").lower() if c.isalnum() or c.isspace()).strip()


def read_answer(text: str) -> str:
    """
    Classify a reply to a confirmation as "yes", "no", or "unclear".

    Deliberately strict. A short utterance is matched whole, so "yes" and
    "yes please" count but a long sentence that merely contains "ok" does
    not — "ok what's on my calendar tomorrow" is a new request, not consent.
    """
    t = _normalise(text)
    if not t:
        return "unclear"
    if t in _AFFIRMATIVE:
        return "yes"
    if t in _NEGATIVE:
        return "no"
    # Allow a leading affirmative only when the whole utterance is short,
    # e.g. "yes do it" — not "yes, and also tell me the weather in Paris".
    words = t.split()
    if len(words) <= 4:
        if words[0] in {"yes", "yeah", "yep", "yup", "sure", "ok", "okay"}:
            return "yes"
        if words[0] in {"no", "nope", "nah", "cancel"}:
            return "no"
    return "unclear"
