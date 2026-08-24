#!/usr/bin/env python3
"""
One-time Google authorisation for Candy (Calendar + Gmail read).

Run this once:

    python scripts/google_setup.py

It opens your browser so YOU sign in to YOUR Google account and grant Candy
permission. The resulting token is written to `api/.secrets/token.json`,
which is gitignored and never served to the browser.

Re-run it any time the requested scopes change — Google requires fresh
consent for new permissions, and an old token simply won't carry them.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from api.services.google_auth import (  # noqa: E402
    CLIENT_SECRET_PATH,
    SCOPES,
    SECRETS_DIR,
    TOKEN_PATH,
)


def main():
    if not os.path.exists(CLIENT_SECRET_PATH):
        raise SystemExit(
            f"client_secret.json not found at {CLIENT_SECRET_PATH}.\n"
            "Download it from Google Cloud Console (APIs & Services > "
            "Credentials > OAuth client ID, type 'Desktop app') and save it "
            "there first."
        )

    os.makedirs(SECRETS_DIR, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    # prompt="consent" forces the scope screen even on re-runs, so a token
    # that predates a newly added scope actually gets upgraded.
    creds = flow.run_local_server(port=0, prompt="consent")

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print("Success. Candy can now read your calendar, create events, and read your mail.")
    print("Granted scopes:")
    for scope in creds.scopes or []:
        print("   ", scope)
    print("Token saved to:", TOKEN_PATH)


if __name__ == "__main__":
    main()
