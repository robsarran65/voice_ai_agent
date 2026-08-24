# ============================================================
# Google OAuth — service layer
# ============================================================
# Shared credential handling for Candy's Calendar and Gmail access.
#
# Modelled on Jarvis 2's `app/google_auth.py`, including its key lesson:
# never force a SCOPES list when *loading* a token. A refresh token can only
# be redeemed for the scopes it was actually granted with, so asking for a
# broader list than the file carries fails at refresh time. `has_scope()`
# reads what the token really has, so callers can hide capabilities the user
# never consented to.
#
# Two deliberate differences from Jarvis 2:
#   * Candy keeps its OWN token file. Sharing Jarvis 2's would mean writing
#     to that project on every refresh, and Jarvis 2 is reference-only.
#   * Gmail is requested read-only. Jarvis 2 holds gmail.modify because it
#     sends and archives mail; Candy only reads, and a token that cannot
#     write is the difference between a prompt-injected email being able to
#     embarrass you and being able to act as you.

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as gbuild

log = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
SECRETS_DIR = os.path.abspath(os.path.join(HERE, "..", ".secrets"))
CLIENT_SECRET_PATH = os.path.join(SECRETS_DIR, "client_secret.json")
TOKEN_PATH = os.path.join(SECRETS_DIR, "token.json")

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SCOPES = [CALENDAR_SCOPE, GMAIL_READ_SCOPE]

SETUP_HINT = (
    "Google isn't authorised yet — run `python scripts/google_setup.py` once, "
    "sign in, and grant access."
)


def is_authorized() -> bool:
    return os.path.exists(TOKEN_PATH)


def has_scope(scope: str) -> bool:
    """
    Whether token.json actually carries a given scope.

    Reads the scopes recorded IN THE FILE rather than assuming SCOPES — a
    token written before a scope was added simply won't have it, and the
    honest answer is False rather than a failure at call time.
    """
    if not os.path.exists(TOKEN_PATH):
        return False
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
        return scope in (creds.scopes or [])
    except Exception as exc:
        log.warning("Could not read token scopes: %s", exc)
        return False


def get_credentials() -> Credentials:
    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(SETUP_HINT)
    # No SCOPES override — use whatever the token was actually granted.
    creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds


def build_service(name: str, version: str):
    return gbuild(name, version, credentials=get_credentials(), cache_discovery=False)
