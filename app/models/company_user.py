"""CompanyUser model — top-level account owner."""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class CompanyUser(Base):
    __tablename__ = "company_users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    company_name = Column(String(150), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agents = relationship(
        "Agent", back_populates="company", cascade="all, delete-orphan"
    )
