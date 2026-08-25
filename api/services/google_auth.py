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

import base64
import json
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


def _env_token_info() -> dict | None:
    """Load Google authorized-user credentials from Vercel-friendly env vars.

    Prefer GOOGLE_TOKEN_JSON_B64 because it is easy to paste into hosting
    dashboards without newline/quote escaping problems. GOOGLE_TOKEN_JSON is
    supported as a plain JSON alternative.
    """
    raw_b64 = (os.getenv("GOOGLE_TOKEN_JSON_B64") or "").strip()
    raw_json = (os.getenv("GOOGLE_TOKEN_JSON") or "").strip()
    try:
        if raw_b64:
            return json.loads(base64.b64decode(raw_b64).decode("utf-8"))
        if raw_json:
            return json.loads(raw_json)
    except Exception as exc:
        log.warning("Could not parse Google token environment variable: %s", exc)
    return None


def _load_credentials() -> tuple[Credentials | None, bool]:
    """Return (credentials, came_from_file)."""
    info = _env_token_info()
    if info:
        return Credentials.from_authorized_user_info(info), False
    if os.path.exists(TOKEN_PATH):
        return Credentials.from_authorized_user_file(TOKEN_PATH), True
    return None, False


def is_authorized() -> bool:
    creds, _ = _load_credentials()
    return creds is not None


def has_scope(scope: str) -> bool:
    """Whether the deployed credential actually carries a given scope."""
    try:
        creds, _ = _load_credentials()
        return creds is not None and scope in (creds.scopes or [])
    except Exception as exc:
        log.warning("Could not read token scopes: %s", exc)
        return False


def get_credentials() -> Credentials:
    creds, came_from_file = _load_credentials()
    if creds is None:
        raise RuntimeError(SETUP_HINT)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Local development can persist a refreshed access token. Hosted
        # serverless environments use the refresh token from the environment
        # on each cold start and never need to write secrets to disk.
        if came_from_file:
            try:
                with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            except OSError as exc:
                log.warning("Could not persist refreshed Google token: %s", exc)
    return creds


def build_service(name: str, version: str):
    return gbuild(name, version, credentials=get_credentials(), cache_discovery=False)
