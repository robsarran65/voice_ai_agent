# ============================================================
# Gmail — service layer (read-only)
# ============================================================
# Mechanics only: list and fetch mail, hand back structured results.
#
# Message parsing follows Jarvis 2's `app/gmail.py` — metadata-format listing,
# case-insensitive header lookup, recursive search for the first text/plain
# part, base64url decode, and a length cap so one long email can't crowd out
# the rest of the prompt.
#
# One behaviour is deliberately NOT carried over: Jarvis 2's `get_message`
# marks the message read as a side effect. That is a write. Candy holds only
# gmail.readonly, so it would fail — and even if it worked, reading your mail
# out loud should not silently change your inbox.
#
# Nothing here can send, reply, label, archive or trash. That is the point:
# email bodies are attacker-controlled text, and the tightest limit on what a
# prompt injection can achieve is a token that cannot write.

import base64
import logging
from dataclasses import dataclass, field

from api.services import google_auth

log = logging.getLogger(__name__)

MAX_BODY_CHARS = 4000


@dataclass(frozen=True)
class MailResult:
    ok: bool
    messages: list = field(default_factory=list)
    message: dict | None = None
    error: str | None = None


def is_ready() -> bool:
    return google_auth.is_authorized() and google_auth.has_scope(google_auth.GMAIL_READ_SCOPE)


def _service():
    return google_auth.build_service("gmail", "v1")


def _header(headers, name: str) -> str:
    """Case-insensitive lookup of one header value from a Gmail headers list."""
    name = name.lower()
    for h in headers or []:
        if h.get("name", "").lower() == name:
            return h.get("value", "")
    return ""


def list_messages(query: str = "is:unread", max_results: int = 10) -> MailResult:
    """
    List messages matching a Gmail search query, with lightweight metadata.

    `query` takes Gmail's own search syntax ("is:unread", "from:alice",
    "newer_than:2d"), so the caller can ask for a slice of the mailbox
    without this module inventing a query language of its own.
    """
    try:
        svc = _service()
        resp = svc.users().messages().list(
            userId="me", q=query, maxResults=max_results).execute()

        out = []
        for item in resp.get("messages", []):
            msg = svc.users().messages().get(
                userId="me", id=item["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]).execute()
            headers = msg.get("payload", {}).get("headers", [])
            out.append({
                "id": msg["id"],
                "subject": _header(headers, "Subject"),
                "from": _header(headers, "From"),
                "date": _header(headers, "Date"),
                "snippet": msg.get("snippet", ""),
            })
    except Exception as exc:
        log.warning("Gmail list failed: %s", exc)
        return MailResult(ok=False, error=str(exc))

    return MailResult(ok=True, messages=out)


def _find_plain_text_part(part):
    """Recursively search a message payload for the first text/plain part."""
    if part.get("mimeType") == "text/plain":
        return part.get("body", {}).get("data")
    for sub in part.get("parts", []) or []:
        data = _find_plain_text_part(sub)
        if data:
            return data
    return None


def get_message(message_id: str) -> MailResult:
    """Fetch one message's headers and plain-text body. Does not mark it read."""
    try:
        msg = _service().users().messages().get(
            userId="me", id=message_id, format="full").execute()
    except Exception as exc:
        log.warning("Gmail fetch failed: %s", exc)
        return MailResult(ok=False, error=str(exc))

    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    data = _find_plain_text_part(payload) if "parts" in payload \
        else payload.get("body", {}).get("data")

    body = base64.urlsafe_b64decode(data + "==").decode("utf-8", "replace") if data else ""
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "…"

    return MailResult(ok=True, message={
        "id": msg["id"],
        "subject": _header(headers, "Subject"),
        "from": _header(headers, "From"),
        "date": _header(headers, "Date"),
        "body": body,
    })
