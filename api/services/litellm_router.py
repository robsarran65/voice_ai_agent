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

from litellm import completion, get_llm_provider

log = logging.getLogger(__name__)

# Which environment variable holds the key for a given litellm provider name.
# A model string decides its own provider ("anthropic/..." vs
# "openrouter/..."), so the primary and fallback model can each authenticate
# against a different service without either one hardcoding the other's key.
_PROVIDER_ENV_VAR = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def _api_key_for(model: str) -> tuple[str | None, str | None]:
    """
    Resolve the right key for a model's provider.

    Read per call rather than at import time: an import-time read forces every
    importer to guarantee `load_dotenv()` already ran, which is what made the
    app entrypoint need its imports below the dotenv call.

    Returns (key, error). error is set when the provider is known but its key
    env var isn't — the caller can report that plainly instead of the request
    failing deep inside the SDK with an auth error that doesn't name the cause.
    """
    try:
        _, provider, _, _ = get_llm_provider(model)
    except Exception:
        provider = None

    env_var = _PROVIDER_ENV_VAR.get(provider)
    if env_var is None:
        return None, f"no known API key env var for provider {provider!r} (model {model!r})"

    key = os.getenv(env_var)
    if not key:
        return None, f"{env_var} is not set"
    return key, None


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
    attempts = [model] + ([fallback_model] if fallback_model else [])
    errors: list[str] = []

    for candidate in attempts:
        # Resolved per candidate: the primary and fallback model can each
        # belong to a different provider, so each needs its own key.
        api_key, key_error = _api_key_for(candidate)
        if key_error:
            # Worth separating from a call failure: this one is a deploy
            # problem, not a flaky provider, and retrying won't fix it — so
            # skip straight to the next candidate instead of calling out.
            log.warning("Skipping %s: %s", candidate, key_error)
            errors.append(f"{candidate}: {key_error}")
            continue

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
