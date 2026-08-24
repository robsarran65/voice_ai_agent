# ============================================================
# LiteLLM Router — service layer
# Voice AI Agent (Low/No-Cost Edition)
# ============================================================
# Owns *how* to call a chat model reliably: provider wiring, the fallback
# attempt, and turning failure into a structured result.
#
# It deliberately owns none of the *why*. Persona, model choice, and what
# the user hears on failure are domain policy and live in
# `api/core/persona.py`, passed in explicitly by the caller.

import logging
import os
from dataclasses import dataclass

from litellm import completion

log = logging.getLogger(__name__)


def _api_key() -> str | None:
    """
    Read the key per call rather than at import time. Import-time reads force
    every importer to guarantee `load_dotenv()` already ran, which is what made
    the app entrypoint need imports below its dotenv call.
    """
    return os.getenv("OPENROUTER_API_KEY")


@dataclass(frozen=True)
class LLMResult:
    """
    Structured outcome of a chat completion.

    Callers must branch on `ok`. The previous version returned the error
    text as if it were the model's reply, so the route had no way to tell
    a real answer from a failure — and spoke the exception aloud.
    """

    ok: bool
    text: str | None = None
    model: str | None = None  # which model actually answered
    error: str | None = None  # operator-facing detail; never spoken to a user


def _attempt(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_text: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """One completion call. Raises on failure — the caller decides what that means."""
    response = completion(
        model=model,
        api_key=api_key,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response["choices"][0]["message"]["content"]


def complete_chat(
    *,
    system_prompt: str,
    user_text: str,
    model: str,
    max_tokens: int,
    temperature: float,
    fallback_model: str | None = None,
) -> LLMResult:
    """
    Run a single-turn chat completion, optionally retrying on a fallback model.

    Every input is explicit — no module-level persona or model defaults — so
    different product flows can share this without sharing each other's policy.
    """
    api_key = _api_key()
    if not api_key:
        # Worth separating from a call failure: this one is a deploy problem,
        # not a flaky provider, and no amount of retrying will fix it.
        return LLMResult(ok=False, error="OPENROUTER_API_KEY is not set")

    attempts = [model] + ([fallback_model] if fallback_model else [])
    errors: list[str] = []

    for candidate in attempts:
        try:
            text = _attempt(
                api_key=api_key,
                model=candidate,
                system_prompt=system_prompt,
                user_text=user_text,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return LLMResult(ok=True, text=text, model=candidate)
        except Exception as exc:
            log.warning("LLM call failed on %s: %s", candidate, exc)
            errors.append(f"{candidate}: {exc}")

    return LLMResult(ok=False, error=" | ".join(errors))
