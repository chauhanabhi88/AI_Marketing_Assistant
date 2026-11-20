"""Application entry point — FastAPI app factory."""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth.dependencies import AuthRedirectException
from .auth.jwt_handler import decode_token
from .config import get_settings
from .database import Base, engine
from .models import Agent, ChatSession, CompanyUser, Conversation, UserToken  # noqa: F401 — register models
from .routes import agent, auth, chat, company

settings = get_settings()

# Create all tables on startup (use Alembic for production migrations)
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(company.router)
app.include_router(agent.router)
app.include_router(chat.router)


@app.exception_handler(AuthRedirectException)
async def auth_redirect_handler(request: Request, _exc: AuthRedirectException):
    """Redirect unauthenticated requests to the login page."""
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard")
async def dashboard_redirect(request: Request):
    """Smart redirect based on the authenticated user's role."""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    payload = decode_token(token)
    if not payload:
        return RedirectResponse(url="/login", status_code=302)

    if payload.get("user_type") == "company":
        return RedirectResponse(url="/company/dashboard", status_code=302)
    return RedirectResponse(url="/agent/dashboard", status_code=302)
