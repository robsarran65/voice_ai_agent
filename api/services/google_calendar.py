# ============================================================
# Google Calendar — service layer
# ============================================================
# Mechanics only: talk to the Calendar API, hand back structured results.
# Whether Candy should create an event, and whether the user confirmed it
# first, is decided in `api/core/`.
#
# Event shape follows Jarvis 2's `app/gcal.py`: ISO 8601 start/end carrying a
# UTC offset, which lets the API infer the time zone so no separate timeZone
# field is needed.

import logging
from dataclasses import dataclass, field

from api.services import google_auth

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalendarResult:
    ok: bool
    events: list = field(default_factory=list)
    event: dict | None = None
    error: str | None = None


def is_ready() -> bool:
    return google_auth.is_authorized() and google_auth.has_scope(google_auth.CALENDAR_SCOPE)


def _service():
    return google_auth.build_service("calendar", "v3")


def _summarise(item: dict) -> dict:
    """Flatten one API event into the few fields worth speaking aloud."""
    start = item.get("start", {})
    end = item.get("end", {})
    return {
        "id": item.get("id"),
        "title": item.get("summary", "Untitled event"),
        # All-day events carry `date`; timed ones carry `dateTime`.
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "all_day": "date" in start,
        "location": item.get("location", ""),
    }


def list_events(time_min_iso: str, time_max_iso: str, max_results: int = 15) -> CalendarResult:
    """Events on the primary calendar within [time_min_iso, time_max_iso)."""
    try:
        result = _service().events().list(
            calendarId="primary",
            timeMin=time_min_iso,
            timeMax=time_max_iso,
            maxResults=max_results,
            singleEvents=True,      # expand recurring series into instances
            orderBy="startTime",
        ).execute()
    except Exception as exc:
        log.warning("Calendar list failed: %s", exc)
        return CalendarResult(ok=False, error=str(exc))

    return CalendarResult(ok=True, events=[_summarise(i) for i in result.get("items", [])])


def create_event(
    *,
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    location: str = "",
) -> CalendarResult:
    """
    Create an event on the primary calendar.

    This writes immediately. Nothing in this module decides whether the user
    agreed to it — that gate lives in the orchestration layer, so the
    confirmation rule is stated once, next to the rest of Candy's policy.
    """
    body = {
        "summary": summary or "Untitled event",
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    try:
        created = _service().events().insert(calendarId="primary", body=body).execute()
    except Exception as exc:
        log.warning("Calendar insert failed: %s", exc)
        return CalendarResult(ok=False, error=str(exc))

    return CalendarResult(ok=True, event=_summarise(created))
