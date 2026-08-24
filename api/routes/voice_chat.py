from fastapi import APIRouter

from api.core.coordinator_agent import CoordinatorAgent
from api.models.request_models import VoiceChatRequest
from api.models.response_models import VoiceChatResponse

router = APIRouter()

# Safe to share: CoordinatorAgent.respond keeps no per-request state.
coordinator = CoordinatorAgent()


@router.post("/", response_model=VoiceChatResponse)
async def voice_chat(request: VoiceChatRequest):
    """
    Main voice-chat endpoint.
    Receives text from Chrome STT, sends it to the agent system,
    and returns the agent's response for Chrome TTS.
    """
    reply = coordinator.respond(request.text)

    # Deliberately 200 even when `reply.ok` is False. The browser speaks
    # whatever comes back, so a 5xx would make it read the response body —
    # status code and JSON braces included — aloud. The friendly line in
    # `reply.message` is the better thing to hear; `ok` carries the real
    # outcome for any caller that cares.
    return VoiceChatResponse(
        ok=reply.ok,
        user_text=request.text,
        agent_task_id=None,
        agent_task_title=None,
        agent_name="Coordinator",
        agent_message=reply.message,
        model=reply.model,
    )
