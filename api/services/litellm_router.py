# ============================================================
# LiteLLM Router — service layer
# Voice AI Agent (Low/No-Cost Edition)
# ============================================================
# Owns *how* to call a chat model reliably: provider wiring, the fallback
# attempt, tool-call plumbing, and turning failure into a structured result.
#
# It owns none of the *why*. Persona, model choice, which tools exist, what
# they do, and what the user hears on failure are all domain policy and live
# in `api/core/`, passed in explicitly by the caller.

import logging
import os
from dataclasses import dataclass, field

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
    Structured outcome of a completion.

    Callers must branch on `ok`. An earlier version returned the error text as
    if it were the model's reply, so the route had no way to tell a real answer
    from a failure — and spoke the exception aloud.

    When the model wants a tool, `tool_calls` is populated and `text` is
    usually empty. `assistant_message` is the raw turn to append to the
    conversation before the tool results, which the provider requires.
    """

    ok: bool
    text: str | None = None
    model: str | None = None
    error: str | None = None
    tool_calls: list = field(default_factory=list)
    assistant_message: dict | None = None


def _attempt(*, api_key, model, messages, max_tokens, temperature, tools):
    """One completion call. Raises on failure — the caller decides what that means."""
    kwargs = dict(
        model=model,
        api_key=api_key,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = completion(**kwargs)
    choice = response["choices"][0]["message"]

    # litellm returns a model object here; normalise to plain dicts so the
    # rest of the app never depends on the SDK's types.
    calls = []
    for call in (getattr(choice, "tool_calls", None) or []):
        calls.append({
            "id": call.id,
            "name": call.function.name,
            "arguments": call.function.arguments,
        })

    assistant = {"role": "assistant", "content": choice.get("content") or ""}
    if calls:
        assistant["tool_calls"] = [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": c["arguments"]}}
            for c in calls
        ]

    return choice.get("content"), calls, assistant


def complete_messages(
    *,
    messages: list,
    model: str,
    max_tokens: int,
    temperature: float,
    fallback_model: str | None = None,
    tools: list | None = None,
) -> LLMResult:
    """
    Run a completion over an explicit message list, optionally offering tools.

    This is the composable primitive: a tool loop needs to send the whole
    conversation back each turn, which a system-prompt-plus-one-string call
    cannot express.
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
            text, calls, assistant = _attempt(
                api_key=api_key,
                model=candidate,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
            )
            return LLMResult(ok=True, text=text, model=candidate,
                             tool_calls=calls, assistant_message=assistant)
        except Exception as exc:
            log.warning("LLM call failed on %s: %s", candidate, exc)
            errors.append(f"{candidate}: {exc}")

    return LLMResult(ok=False, error=" | ".join(errors))


def complete_chat(
    *,
    system_prompt: str,
    user_text: str,
    model: str,
    max_tokens: int,
    temperature: float,
    fallback_model: str | None = None,
) -> LLMResult:
    """Single-turn convenience wrapper over `complete_messages`."""
    return complete_messages(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        fallback_model=fallback_model,
    )
