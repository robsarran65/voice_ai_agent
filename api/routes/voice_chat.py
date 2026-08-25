from fastapi import APIRouter, Header, HTTPException

from api.core.coordinator_agent import CoordinatorAgent
from api.core.tenant_config import get_tenant
from api.models.request_models import VoiceChatRequest
from api.models.response_models import VoiceChatResponse

router = APIRouter()
coordinator = CoordinatorAgent()


@router.post("/", response_model=VoiceChatResponse)
async def voice_chat(request: VoiceChatRequest, x_munai_tenant: str | None = Header(default=None)):
    """Multi-tenant web voice endpoint with per-turn cost telemetry."""
    tenant_id = x_munai_tenant or request.tenant_id
    try:
        settings = get_tenant(tenant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    reply = coordinator.respond(
        request.text,
        session_id=request.session_id or "",
        settings=settings,
    )
    return VoiceChatResponse(
        ok=reply.ok,
        user_text=request.text,
        agent_task_id=None,
        agent_task_title=None,
        agent_name=settings.assistant_name,
        agent_message=reply.message,
        model=reply.model,
        input_tokens=reply.input_tokens,
        output_tokens=reply.output_tokens,
        cached_input_tokens=reply.cached_input_tokens,
        cost_usd=reply.cost_usd,
        latency_ms=reply.latency_ms,
        fallback_used=reply.fallback_used,
        llm_calls=reply.llm_calls,
        cost_path=reply.cost_path,
    )
