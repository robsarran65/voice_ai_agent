from pydantic import BaseModel


class VoiceChatResponse(BaseModel):
    # False when the reply came from the failure path rather than the model.
    # `agent_message` is always safe to speak aloud either way.
    ok: bool = True
    user_text: str
    agent_task_id: str | None = None
    agent_task_title: str | None = None
    agent_name: str | None = None
    agent_message: str | None = None
    # Which model actually answered — the fallback may have handled it.
    model: str | None = None
