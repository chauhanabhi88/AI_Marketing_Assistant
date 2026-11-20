"""Company user Pydantic schemas."""

from pydantic import BaseModel, EmailStr
from datetime import datetime


class CompanyUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    company_name: str


class CompanyUserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    email: str
    company_name: str
    created_at: datetime
