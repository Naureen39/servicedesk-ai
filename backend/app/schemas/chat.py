from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    conversation_id: str
    text: str = Field(min_length=1, max_length=1000)


class ChatFeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    helpful: bool
