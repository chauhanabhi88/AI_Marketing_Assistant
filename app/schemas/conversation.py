"""Conversation Pydantic schemas."""

from pydantic import BaseModel
from datetime import datetime


class ChatMessage(BaseModel):
    message: str


class ConversationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_type: str
    user_id: int
    message: str
    response: str
    created_at: datetime
