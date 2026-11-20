"""Agent Pydantic schemas."""

from pydantic import BaseModel, EmailStr
from datetime import datetime


class AgentCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class AgentUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None


class AgentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    company_id: int
    name: str
    email: str
    created_at: datetime
