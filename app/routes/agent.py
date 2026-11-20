"""Agent routes: dashboard and conversation history."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_agent
from ..database import get_db
from ..models import Agent, Conversation

router = APIRouter(prefix="/agent", tags=["agent"])
templates = Jinja2Templates(directory="app/templates")

_PAGE_SIZE = 15


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
):
    conv_count = db.query(Conversation).filter(
        Conversation.user_type == "agent",
        Conversation.user_id == current_agent.id,
    ).count()

    recent = (
        db.query(Conversation)
        .filter(
            Conversation.user_type == "agent",
            Conversation.user_id == current_agent.id,
        )
        .order_by(Conversation.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "agent/dashboard.html",
        {
            "user": current_agent,
            "user_type": "agent",
            "conv_count": conv_count,
            "recent": recent,
        },
    )


@router.get("/conversations", response_class=HTMLResponse)
async def my_conversations(
    request: Request,
    db: Session = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
    search: str = "",
    page: int = 1,
):
    query = db.query(Conversation).filter(
        Conversation.user_type == "agent",
        Conversation.user_id == current_agent.id,
    )

    if search:
        like = f"%{search}%"
        query = query.filter(
            Conversation.message.like(like) | Conversation.response.like(like)
        )

    total = query.count()
    pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = max(1, min(page, pages))
    conversations = (
        query.order_by(Conversation.created_at.desc())
        .offset((page - 1) * _PAGE_SIZE)
        .limit(_PAGE_SIZE)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "agent/conversations.html",
        {
            "user": current_agent,
            "user_type": "agent",
            "conversations": conversations,
            "total": total,
            "page": page,
            "pages": pages,
            "search": search,
        },
    )
