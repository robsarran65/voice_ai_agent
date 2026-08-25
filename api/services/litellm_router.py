# ============================================================
# LiteLLM Router — cost-instrumented service layer
# ============================================================
import json
import logging
import os
import time
from dataclasses import dataclass, field

import litellm
from litellm import completion, get_llm_provider

log = logging.getLogger(__name__)
_FAILURE_COOLDOWN_S = 30
_recent_failures: dict[str, float] = {}
litellm.drop_params = True

_PROVIDER_ENV_VAR = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def _recently_failed(model: str) -> bool:
    failed_at = _recent_failures.get(model)
    return failed_at is not None and (time.time() - failed_at) < _FAILURE_COOLDOWN_S


def _api_key_for(model: str) -> tuple[str | None, str | None]:
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


def _usage_value(usage, name: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(name) or 0)
    return int(getattr(usage, name, 0) or 0)


@dataclass(frozen=True)
class LLMResult:
    ok: bool
    text: str | None = None
    model: str | None = None
    error: str | None = None
    tool_calls: list = field(default_factory=list)
    assistant_message: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    fallback_used: bool = False
    cached_input_tokens: int = 0


def _attempt(*, api_key, model, messages, max_tokens, temperature, tools, prompt_cache_key=None):
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
    if prompt_cache_key:
        kwargs["prompt_cache_key"] = prompt_cache_key[:64]

    started = time.perf_counter()
    response = completion(**kwargs)
    latency_ms = round((time.perf_counter() - started) * 1000)
    choice = response["choices"][0]["message"]

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

    usage = getattr(response, "usage", None) or response.get("usage")
    input_tokens = _usage_value(usage, "prompt_tokens")
    output_tokens = _usage_value(usage, "completion_tokens")
    details = None
    if usage is not None:
        details = usage.get("prompt_tokens_details") if isinstance(usage, dict) else getattr(usage, "prompt_tokens_details", None)
    cached_input_tokens = _usage_value(details, "cached_tokens")
    try:
        cost_usd = float(litellm.completion_cost(completion_response=response) or 0.0)
    except Exception:
        cost_usd = 0.0

    return (choice.get("content"), calls, assistant, input_tokens,
            output_tokens, cached_input_tokens, cost_usd, latency_ms)


def _emit_cost_event(*, model: str, input_tokens: int, output_tokens: int,
                     cached_input_tokens: int, cost_usd: float, latency_ms: int,
                     fallback_used: bool) -> None:
    log.info("llm_cost %s", json.dumps({
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cost_usd": round(cost_usd, 8),
        "latency_ms": latency_ms,
        "fallback_used": fallback_used,
    }, separators=(",", ":")))


def complete_messages(*, messages: list, model: str, max_tokens: int,
                      temperature: float, fallback_model: str | None = None,
                      tools: list | None = None, prompt_cache_key: str | None = None) -> LLMResult:
    attempts = [model] + ([fallback_model] if fallback_model else [])
    errors: list[str] = []

    for index, candidate in enumerate(attempts):
        if _recently_failed(candidate):
            errors.append(f"{candidate}: skipped (failed recently)")
            continue

        api_key, key_error = _api_key_for(candidate)
        if key_error:
            log.warning("Skipping %s: %s", candidate, key_error)
            errors.append(f"{candidate}: {key_error}")
            continue

        try:
            text, calls, assistant, in_tok, out_tok, cached_tok, cost, latency = _attempt(
                api_key=api_key, model=candidate, messages=messages,
                max_tokens=max_tokens, temperature=temperature, tools=tools,
                prompt_cache_key=prompt_cache_key,
            )
            _recent_failures.pop(candidate, None)
            fallback_used = index > 0
            _emit_cost_event(model=candidate, input_tokens=in_tok,
                             output_tokens=out_tok, cached_input_tokens=cached_tok,
                             cost_usd=cost, latency_ms=latency,
                             fallback_used=fallback_used)
            # A model can technically return a successful HTTP response with
            # neither text nor a tool call. Do not propagate that as an empty
            # voice response; try the fallback model instead.
            if not calls and not (text or "").strip():
                errors.append(f"{candidate}: empty response")
                log.warning("LLM returned empty response on %s; trying fallback", candidate)
                continue

            return LLMResult(
                ok=True, text=text, model=candidate, tool_calls=calls,
                assistant_message=assistant, input_tokens=in_tok,
                output_tokens=out_tok, cost_usd=cost, latency_ms=latency,
                fallback_used=fallback_used, cached_input_tokens=cached_tok,
            )
        except Exception as exc:
            log.warning("LLM call failed on %s: %s", candidate, exc)
            errors.append(f"{candidate}: {exc}")
            _recent_failures[candidate] = time.time()

    return LLMResult(ok=False, error=" | ".join(errors))


def complete_chat(*, system_prompt: str, user_text: str, model: str,
                  max_tokens: int, temperature: float,
                  fallback_model: str | None = None) -> LLMResult:
    return complete_messages(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        model=model, max_tokens=max_tokens, temperature=temperature,
        fallback_model=fallback_model,
    )
