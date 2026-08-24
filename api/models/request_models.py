from pydantic import BaseModel


class VoiceChatRequest(BaseModel):
    text: str
