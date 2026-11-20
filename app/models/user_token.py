"""UserToken model — persists issued JWT tokens for server-side revocation."""

from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from ..database import Base


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    user_type = Column(Enum("company", "agent"), nullable=False)
    token = Column(String(512), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
