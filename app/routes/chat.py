"""Chat routes — multi-session AI conversations with SSE streaming."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user_any
from ..database import get_db
from ..models import Conversation
from ..models.chat_session import ChatSession
from ..services.ai_service import stream_ai_response

router = APIRouter(prefix="/chat", tags=["chat"])
templates = Jinja2Templates(directory="app/templates")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _generate_title(message: str) -> str:
    """Derive a session title from the first user message (max 55 chars)."""
    text = message.strip()
    if len(text) <= 55:
        return text
    truncated = text[:55].rsplit(" ", 1)[0]
    return truncated + "…"


def _get_session_or_404(
    db: Session,
    session_id: int,
    user_type: str,
    user_id: int,
) -> ChatSession:
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_type == user_type,
        ChatSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return session


def _session_to_dict(s: ChatSession, message_count: int) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "message_count": message_count,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat() if s.updated_at else s.created_at.isoformat(),
    }


# ── Chat page (HTML) ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def chat_page(
    request: Request,
    db: Session = Depends(get_db),
    user_info: tuple = Depends(get_current_user_any),
):
    user_type, user = user_info
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_type == user_type, ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "chat/chat.html",
        {"user": user, "user_type": user_type, "sessions": sessions},
    )


# ── Session list (JSON) ────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    db: Session = Depends(get_db),
    user_info: tuple = Depends(get_current_user_any),
):
    user_type, user = user_info

    # Count messages per session in one query
    counts = dict(
        db.query(Conversation.session_id, func.count(Conversation.id))
        .filter(
            Conversation.user_type == user_type,
            Conversation.user_id == user.id,
            Conversation.session_id.isnot(None),
        )
        .group_by(Conversation.session_id)
        .all()
    )

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_type == user_type, ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    return [_session_to_dict(s, counts.get(s.id, 0)) for s in sessions]


# ── Create new session ─────────────────────────────────────────────────────────

@router.post("/sessions/new")
async def new_session(
    db: Session = Depends(get_db),
    user_info: tuple = Depends(get_current_user_any),
):
    user_type, user = user_info
    session = ChatSession(user_type=user_type, user_id=user.id, title="New Chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_dict(session, 0)


# ── Get session messages (JSON) ────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    user_info: tuple = Depends(get_current_user_any),
):
    user_type, user = user_info
    session = _get_session_or_404(db, session_id, user_type, user.id)

    messages = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.created_at.asc())
        .all()
    )

    return {
        "session": _session_to_dict(session, len(messages)),
        "messages": [
            {
                "id": m.id,
                "message": m.message,
                "response": m.response,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


# ── Delete a session ───────────────────────────────────────────────────────────

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    user_info: tuple = Depends(get_current_user_any),
):
    user_type, user = user_info
    session = _get_session_or_404(db, session_id, user_type, user.id)
    db.delete(session)
    db.commit()
    return {"deleted": True}


# ── Rename a session ───────────────────────────────────────────────────────────

@router.patch("/sessions/{session_id}/title")
async def rename_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user_info: tuple = Depends(get_current_user_any),
):
    user_type, user = user_info
    session = _get_session_or_404(db, session_id, user_type, user.id)
    data = await request.json()
    title = str(data.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    session.title = title[:100]
    db.commit()
    return {"id": session.id, "title": session.title}


# ── Streaming send ─────────────────────────────────────────────────────────────

@router.post("/send/stream")
async def send_message_stream(
    request: Request,
    db: Session = Depends(get_db),
    user_info: tuple = Depends(get_current_user_any),
):
    user_type, user = user_info
    data = await request.json()
    message = str(data.get("message", "")).strip()
    session_id: int | None = data.get("session_id")

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Resolve session — create one if none provided
    if session_id:
        session = _get_session_or_404(db, session_id, user_type, user.id)
    else:
        session = ChatSession(user_type=user_type, user_id=user.id, title="New Chat")
        db.add(session)
        db.flush()  # get the id without committing

    # Build history from this session only
    history = [
        {"message": c.message, "response": c.response}
        for c in (
            db.query(Conversation)
            .filter(Conversation.session_id == session.id)
            .order_by(Conversation.created_at.desc())
            .limit(10)
            .all()
        )[::-1]
    ]

    is_first_message = len(history) == 0
    collected: list[str] = []

    async def event_generator():
        # Signal the session id to the client (useful when auto-created)
        yield f"data: {json.dumps({'session_id': session.id})}\n\n"

        try:
            async for token in stream_ai_response(message, history):
                collected.append(token)
                yield f"data: {json.dumps({'content': token})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            return

        # Persist conversation
        full_response = "".join(collected)
        conv = Conversation(
            session_id=session.id,
            user_type=user_type,
            user_id=user.id,
            message=message,
            response=full_response,
        )
        db.add(conv)

        # Auto-title from first message; also bump updated_at
        if is_first_message and session.title == "New Chat":
            session.title = _generate_title(message)
        session.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(conv)

        yield f"data: {json.dumps({'done': True, 'id': conv.id, 'title': session.title})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
