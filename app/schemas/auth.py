"""Authentication request/response schemas."""

from pydantic import BaseModel, EmailStr
from enum import Enum


class UserType(str, Enum):
    company = "company"
    agent = "agent"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    user_type: UserType


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str
    user_name: str
