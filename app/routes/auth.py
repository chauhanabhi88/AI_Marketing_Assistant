"""Authentication routes: login, logout, register."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..auth.jwt_handler import create_access_token
from ..config import get_settings
from ..database import get_db
from ..models import Agent, CompanyUser
from ..models.user_token import UserToken

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


# ── Login ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/dashboard", status_code=302)
    registered = request.query_params.get("registered")
    return templates.TemplateResponse(
        request, "login.html", {"registered": registered}
    )


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    user_type = str(form.get("user_type", "company"))

    if user_type == "company":
        user = db.query(CompanyUser).filter(CompanyUser.email == email).first()
    else:
        user = db.query(Agent).filter(Agent.email == email).first()

    if not user or not pwd_context.verify(password, user.password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password."},
            status_code=400,
        )

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token = create_access_token(
        {"user_id": user.id, "user_type": user_type, "email": user.email}
    )

    # Remove any expired tokens for this user before adding the new one
    db.query(UserToken).filter(
        UserToken.user_id == user.id,
        UserToken.user_type == user_type,
        UserToken.expires_at <= datetime.now(timezone.utc),
    ).delete()

    db.add(UserToken(
        user_id=user.id,
        user_type=user_type,
        token=token,
        expires_at=expires_at,
    ))
    db.commit()

    redirect_url = "/company/dashboard" if user_type == "company" else "/agent/dashboard"
    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    return response


# ── Logout ─────────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if token:
        db.query(UserToken).filter(UserToken.token == token).delete()
        db.commit()
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ── Register ───────────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {})


@router.post("/register")
async def register(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    email = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))
    company_name = str(form.get("company_name", "")).strip()

    if db.query(CompanyUser).filter(CompanyUser.email == email).first():
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Email is already registered."},
            status_code=400,
        )

    user = CompanyUser(
        name=name,
        email=email,
        password=pwd_context.hash(password),
        company_name=company_name,
    )
    db.add(user)
    db.commit()
    return RedirectResponse(url="/login?registered=true", status_code=302)
