from pydantic import BaseModel, ConfigDict


class VoiceChatRequest(BaseModel):
    text: str
    # Identifies one browser tab, so a calendar event proposed on one turn can
    # be confirmed on the next. Optional: without it Candy still answers, she
    # just can't carry a pending confirmation across requests.
    session_id: str | None = None
    # SaaS tenant selector. Prefer the X-MunAI-Tenant header in production;
    # this field is convenient for demos and direct API clients.
    tenant_id: str | None = None


class VapiChatRequest(BaseModel):
    """
    Vapi's custom-LLM request body (POST to the URL configured as the
    assistant's "Custom LLM URL"). Loosely typed on purpose: Vapi's own docs
    don't publish one authoritative full schema — confirmed directly against
    their docs, which describe the shape in prose and point to example repos
    rather than a schema reference — and the payload carries several
    OpenAI-passthrough fields (temperature, stream, tools, ...) this app
    doesn't need to name individually. `extra="allow"` means a field from a
    future Vapi API version doesn't break parsing.
    """

    model_config = ConfigDict(extra="allow")

    messages: list[dict] = []
    call: dict = {}
