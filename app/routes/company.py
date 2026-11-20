"""Company user routes: dashboard, agent management, conversation viewer."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_company_user
from ..database import get_db
from ..models import Agent, CompanyUser, Conversation
from ..models.chat_session import ChatSession

router = APIRouter(prefix="/company", tags=["company"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_PAGE_SIZE = 15


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_company_user),
):
    agent_count = db.query(Agent).filter(Agent.company_id == current_user.id).count()

    agent_ids = [
        row[0]
        for row in db.query(Agent.id).filter(Agent.company_id == current_user.id).all()
    ]

    own_convs = db.query(Conversation).filter(
        Conversation.user_type == "company", Conversation.user_id == current_user.id
    ).count()

    agent_convs = 0
    if agent_ids:
        agent_convs = db.query(Conversation).filter(
            Conversation.user_type == "agent",
            Conversation.user_id.in_(agent_ids),
        ).count()

    total_convs = own_convs + agent_convs

    recent = (
        db.query(Conversation)
        .filter(
            Conversation.user_type == "company",
            Conversation.user_id == current_user.id,
        )
        .order_by(Conversation.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "company/dashboard.html",
        {
            "user": current_user,
            "user_type": "company",
            "agent_count": agent_count,
            "total_convs": total_convs,
            "recent": recent,
        },
    )


# ── Agent management ───────────────────────────────────────────────────────────

@router.get("/agents", response_class=HTMLResponse)
async def list_agents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_company_user),
):
    agents = (
        db.query(Agent)
        .filter(Agent.company_id == current_user.id)
        .order_by(Agent.created_at.desc())
        .all()
    )
    msg = request.query_params.get("msg")
    return templates.TemplateResponse(
        request,
        "company/agents.html",
        {"user": current_user, "user_type": "company", "agents": agents, "msg": msg},
    )


@router.post("/agents/create")
async def create_agent(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_company_user),
):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))

    if db.query(Agent).filter(Agent.email == email).first():
        agents = db.query(Agent).filter(Agent.company_id == current_user.id).all()
        return templates.TemplateResponse(
            request,
            "company/agents.html",
            {
                "user": current_user,
                "user_type": "company",
                "agents": agents,
                "error": "An agent with this email already exists.",
            },
            status_code=400,
        )

    agent = Agent(
        company_id=current_user.id,
        name=name,
        email=email,
        password=pwd_context.hash(password),
    )
    db.add(agent)
    db.commit()
    return RedirectResponse(url="/company/agents?msg=created", status_code=302)


@router.post("/agents/{agent_id}/update")
async def update_agent(
    agent_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_company_user),
):
    agent = db.query(Agent).filter(
        Agent.id == agent_id, Agent.company_id == current_user.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    form = await request.form()
    if name := str(form.get("name", "")).strip():
        agent.name = name
    if email := str(form.get("email", "")).strip().lower():
        agent.email = email
    if password := str(form.get("password", "")):
        agent.password = pwd_context.hash(password)

    db.commit()
    return RedirectResponse(url="/company/agents?msg=updated", status_code=302)


@router.post("/agents/{agent_id}/delete")
async def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_company_user),
):
    agent = db.query(Agent).filter(
        Agent.id == agent_id, Agent.company_id == current_user.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    db.delete(agent)
    db.commit()
    return RedirectResponse(url="/company/agents?msg=deleted", status_code=302)


# ── Conversations ──────────────────────────────────────────────────────────────

def _get_agent_ids(db: Session, company_id: int) -> list[int]:
    return [row[0] for row in db.query(Agent.id).filter(Agent.company_id == company_id).all()]


def _agents_map(db: Session, agent_ids: list[int]) -> dict[int, Agent]:
    if not agent_ids:
        return {}
    return {a.id: a for a in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()}


def _session_access_filter(company_user_id: int, agent_ids: list[int]):
    conditions = [
        and_(ChatSession.user_type == "company", ChatSession.user_id == company_user_id)
    ]
    if agent_ids:
        conditions.append(
            and_(ChatSession.user_type == "agent", ChatSession.user_id.in_(agent_ids))
        )
    return or_(*conditions)


@router.get("/conversations", response_class=HTMLResponse)
async def view_conversations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_company_user),
):
    agent_ids = _get_agent_ids(db, current_user.id)

    sessions = (
        db.query(ChatSession)
        .filter(_session_access_filter(current_user.id, agent_ids))
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    session_ids = [s.id for s in sessions]
    counts: dict[int, int] = {}
    if session_ids:
        counts = dict(
            db.query(Conversation.session_id, func.count(Conversation.id))
            .filter(Conversation.session_id.in_(session_ids))
            .group_by(Conversation.session_id)
            .all()
        )

    return templates.TemplateResponse(
        request,
        "company/conversations.html",
        {
            "user": current_user,
            "user_type": "company",
            "sessions": sessions,
            "agents_map": _agents_map(db, agent_ids),
            "counts": counts,
            "total": len(sessions),
        },
    )


@router.get("/conversations/{session_id}", response_class=HTMLResponse)
async def view_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CompanyUser = Depends(get_current_company_user),
):
    agent_ids = _get_agent_ids(db, current_user.id)

    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        _session_access_filter(current_user.id, agent_ids),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    conversations = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.created_at.asc())
        .all()
    )

    amap = _agents_map(db, agent_ids)
    if session.user_type == "company":
        owner_name = current_user.name
        owner_type = "company"
    else:
        owner = amap.get(session.user_id)
        owner_name = owner.name if owner else f"Agent #{session.user_id}"
        owner_type = "agent"

    return templates.TemplateResponse(
        request,
        "company/session_detail.html",
        {
            "user": current_user,
            "user_type": "company",
            "session": session,
            "conversations": conversations,
            "owner_name": owner_name,
            "owner_type": owner_type,
        },
    )
