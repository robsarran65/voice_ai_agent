from pydantic import BaseModel


class VoiceChatResponse(BaseModel):
    ok: bool = True
    user_text: str
    agent_task_id: str | None = None
    agent_task_title: str | None = None
    agent_name: str | None = None
    agent_message: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    fallback_used: bool = False
    llm_calls: int = 0
    cost_path: str = "llm"
