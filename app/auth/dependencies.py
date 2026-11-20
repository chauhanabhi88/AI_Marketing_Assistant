"""FastAPI dependency helpers for authentication."""

from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Agent, CompanyUser
from ..models.user_token import UserToken
from .jwt_handler import decode_token


class AuthRedirectException(Exception):
    """Raised when authentication is required but the token is missing or invalid."""
    pass


def _extract_payload(request: Request, db: Session) -> dict | None:
    """Read the cookie token, validate the JWT, then verify it exists in the DB."""
    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = decode_token(token)
    if not payload:
        return None

    db_token = db.query(UserToken).filter(
        UserToken.token == token,
        UserToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if not db_token:
        return None

    return payload


def get_current_company_user(
    request: Request,
    db: Session = Depends(get_db),
) -> CompanyUser:
    """Dependency for routes that require a logged-in company user."""
    payload = _extract_payload(request, db)
    if not payload or payload.get("user_type") != "company":
        raise AuthRedirectException()

    user = db.query(CompanyUser).filter(CompanyUser.id == payload["user_id"]).first()
    if not user:
        raise AuthRedirectException()
    return user


def get_current_agent(
    request: Request,
    db: Session = Depends(get_db),
) -> Agent:
    """Dependency for routes that require a logged-in agent."""
    payload = _extract_payload(request, db)
    if not payload or payload.get("user_type") != "agent":
        raise AuthRedirectException()

    agent = db.query(Agent).filter(Agent.id == payload["user_id"]).first()
    if not agent:
        raise AuthRedirectException()
    return agent


def get_current_user_any(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[str, CompanyUser | Agent]:
    """Dependency that accepts either user type; returns (user_type, user)."""
    payload = _extract_payload(request, db)
    if not payload:
        raise AuthRedirectException()

    user_type: str = payload.get("user_type", "")
    user_id: int = payload.get("user_id", 0)

    if user_type == "company":
        user = db.query(CompanyUser).filter(CompanyUser.id == user_id).first()
    elif user_type == "agent":
        user = db.query(Agent).filter(Agent.id == user_id).first()
    else:
        raise AuthRedirectException()

    if not user:
        raise AuthRedirectException()
    return user_type, user
