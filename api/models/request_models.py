from pydantic import BaseModel


class VoiceChatRequest(BaseModel):
    text: str
    # Identifies one browser tab, so a calendar event proposed on one turn can
    # be confirmed on the next. Optional: without it Candy still answers, she
    # just can't carry a pending confirmation across requests.
    session_id: str | None = None
