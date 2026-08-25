# ============================================================
# Phone route — Vapi custom-LLM adapter
# ============================================================
# Vapi owns the phone number, call audio, speech-to-text and text-to-speech.
# It calls THIS endpoint once per conversational turn with a plain HTTP POST
# shaped like OpenAI's /chat/completions, and speaks back whatever text this
# returns. No persistent connection on our side — this is why Vapi, and not
# a raw telephony + WebSocket-audio-bridge provider, is what this project
# uses: it's the one option that runs on the same host as everything else
# (confirmed against Vapi's own docs, which publish a Vercel serverless
# example of exactly this pattern).
#
# DORMANT BY DEFAULT. Both env vars this file reads are unset until someone
# deliberately configures them:
#   - VAPI_SERVER_SECRET unset  -> every request gets 401. No number has to
#     exist yet for this route to be safe to ship.
#   - CANDY_ALLOWED_CALLERS unset -> even once authorized, no caller is
#     trusted, so calendar/email stay hidden for everyone until a real
#     number is added to the allowlist.
# See ROADMAP.md for the activation steps this file assumes.

import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request

from api.core.coordinator_agent import CoordinatorAgent
from api.core.history import compact_phone_history
from api.core.tenant_config import get_tenant, tenant_for_vapi_assistant
from api.models.request_models import VapiChatRequest

log = logging.getLogger(__name__)
router = APIRouter()

# Safe to share: CoordinatorAgent.respond keeps no per-request state.
coordinator = CoordinatorAgent()


def _authorized(request: Request) -> bool:
    """
    Confirm this request actually came from our configured Vapi assistant.

    Checks both auth styles Vapi's docs describe: the current recommended
    `Authorization: Bearer <token>`, and the legacy `X-Vapi-Secret` header
    kept for backward compatibility. An unset secret means the feature was
    never configured — refuse everything rather than compare against "".
    """
    secret = os.getenv("VAPI_SERVER_SECRET")
    if not secret:
        return False

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[len("Bearer "):] == secret:
        return True
    return request.headers.get("x-vapi-secret", "") == secret


def _extract_caller_number(call: dict) -> str | None:
    """
    Best-effort read of the caller's number out of Vapi's call metadata.

    Vapi's own docs disagree with themselves here: the Call-object schema
    used by their Create/Get Call API documents `customer.number`, while
    Vapi's own spam-call-rejection example reads `from.phoneNumber` for an
    inbound webhook. Both are tried rather than picking one and guessing
    wrong. Confirm which one (or both) actually appears on a real Custom LLM
    request during activation testing, and simplify this once known.
    """
    customer = call.get("customer") or {}
    if customer.get("number"):
        return customer["number"]
    frm = call.get("from") or {}
    if frm.get("phoneNumber"):
        return frm["phoneNumber"]
    return None


def _is_trusted_caller(call: dict, settings) -> bool:
    """Tenant-scoped phone allowlist for private calendar/email tools."""
    allowed = set(settings.trusted_callers)
    if not allowed:
        return False
    caller = _extract_caller_number(call)
    return caller is not None and caller in allowed


def _openai_shaped(text: str, model: str | None, *, input_tokens: int = 0, output_tokens: int = 0) -> dict:
    """Minimum valid OpenAI chat-completion object — what Vapi expects back."""
    now = int(time.time())
    return {
        "id": f"chatcmpl-candy-{now}",
        "object": "chat.completion",
        "created": now,
        "model": model or "candy",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }


@router.post("/chat/completions")
async def phone_chat_completions(request: Request):
    """
    Vapi's Custom LLM URL target. One call per conversational turn.

    Deliberately never streams the response (always one complete JSON
    object) — Vapi's docs confirm this is accepted, and it matches
    CoordinatorAgent.respond's synchronous shape, so no new streaming
    plumbing is needed just for the phone path.
    """
    if not _authorized(request):
        log.warning("Rejected an unauthorized /phone/chat/completions request")
        raise HTTPException(status_code=401, detail="unauthorized")

    body = await request.json()
    vapi_request = VapiChatRequest(**body)

    messages = vapi_request.messages
    call = vapi_request.call
    session_id = call.get("id") or ""
    requested_tenant = request.headers.get("x-munai-tenant")
    try:
        if requested_tenant:
            settings = get_tenant(requested_tenant)
        else:
            assistant = call.get("assistant") or {}
            settings = tenant_for_vapi_assistant(assistant.get("id"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    trusted = _is_trusted_caller(call, settings)

    # Vapi resends the whole transcript every turn, newest message last.
    # Everything before it is prior conversation; a stray system message
    # from Vapi is dropped rather than passed through, since our own
    # coordinator supplies its own persona as the system prompt.
    if messages and messages[-1].get("role") == "user":
        user_text = messages[-1].get("content", "")
        raw_history = [m for m in messages[:-1] if m.get("role") in ("user", "assistant")]
        history, history_summary = compact_phone_history(
            raw_history, recent_messages=settings.recent_history_messages,
            summary_chars=settings.history_summary_chars,
        )
    else:
        # No fresh user turn to answer yet — e.g. Vapi's own setup/handshake
        # calls. Nothing to say.
        user_text = ""
        raw_history = [m for m in messages if m.get("role") in ("user", "assistant")]
        history, history_summary = compact_phone_history(
            raw_history, recent_messages=settings.recent_history_messages,
            summary_chars=settings.history_summary_chars,
        )

    reply = coordinator.respond(
        user_text, session_id=session_id, history=history, trusted=trusted,
        history_summary=history_summary, settings=settings,
    )

    log.info(
        "phone_turn_cost session=%s model=%s llm_calls=%d input_tokens=%d output_tokens=%d cost_usd=%.8f latency_ms=%d path=%s",
        session_id, reply.model, reply.llm_calls, reply.input_tokens,
        reply.output_tokens, reply.cost_usd, reply.latency_ms, reply.cost_path,
    )
    return _openai_shaped(
        reply.message, reply.model, input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
    )
