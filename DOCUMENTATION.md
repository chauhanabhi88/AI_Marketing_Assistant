# AI Marketing Strategy Assistant — Technical Documentation

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Database Schema](#4-database-schema)
5. [Authentication & Session Flow](#5-authentication--session-flow)
6. [Application Flow by Role](#6-application-flow-by-role)
7. [AI Chat Flow (SSE Streaming)](#7-ai-chat-flow-sse-streaming)
8. [API Endpoints Reference](#8-api-endpoints-reference)
9. [Key Components](#9-key-components)
10. [Configuration Reference](#10-configuration-reference)
11. [Frontend Architecture](#11-frontend-architecture)
12. [Security Design](#12-security-design)

---

## 1. Project Overview

A multi-user AI-powered marketing assistant web application built with FastAPI and Google Gemini. It supports two user roles:

- **Company User** — registers an account, manages a team of agents, and views all chat sessions across their organisation.
- **Agent** — a limited-access user created by a Company User, who can chat with the AI assistant and view their own conversation history.

Both roles share the same chat interface but have separate dashboards with role-appropriate features.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115+ |
| Templating | Jinja2 + Bootstrap 5.3 |
| Database ORM | SQLAlchemy 2.0 |
| Database | MySQL 8 (via PyMySQL) |
| AI provider | Google Gemini (`gemini-2.0-flash`) |
| Authentication | JWT (python-jose) + bcrypt (passlib) |
| Password hashing | bcrypt 4.0 |
| Config management | pydantic-settings |
| Frontend JS | Vanilla JavaScript (no framework) |
| CSS framework | Bootstrap 5.3 + Bootstrap Icons |
| Server | Uvicorn (ASGI) |

---

## 3. Project Structure

```
sample/
│
├── app/
│   ├── main.py                  # FastAPI app factory, router registration
│   ├── config.py                # Environment settings (Pydantic Settings)
│   ├── database.py              # SQLAlchemy engine + session factory
│   │
│   ├── auth/
│   │   ├── jwt_handler.py       # JWT create / decode
│   │   └── dependencies.py      # FastAPI auth dependency injectors
│   │
│   ├── models/
│   │   ├── __init__.py          # Re-exports all models
│   │   ├── company_user.py      # CompanyUser ORM model
│   │   ├── agent.py             # Agent ORM model
│   │   ├── chat_session.py      # ChatSession ORM model
│   │   ├── conversation.py      # Conversation ORM model
│   │   └── user_token.py        # UserToken ORM model (JWT revocation)
│   │
│   ├── routes/
│   │   ├── auth.py              # /login  /logout  /register
│   │   ├── company.py           # /company/*
│   │   ├── agent.py             # /agent/*
│   │   └── chat.py              # /chat/*
│   │
│   ├── services/
│   │   └── ai_service.py        # Google Gemini streaming integration
│   │
│   ├── templates/
│   │   ├── base.html            # Shared layout (sidebar, topbar)
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── company/
│   │   │   ├── dashboard.html
│   │   │   ├── agents.html
│   │   │   ├── conversations.html   # Session list
│   │   │   └── session_detail.html  # Single session Q&A view
│   │   ├── agent/
│   │   │   ├── dashboard.html
│   │   │   └── conversations.html
│   │   └── chat/
│   │       └── chat.html        # Live chat UI
│   │
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── main.js          # Dark mode + sidebar toggle
│           └── chat.js          # ChatApp class (multi-session UI)
│
├── requirements.txt
├── .env                         # Secret config (not committed)
└── DOCUMENTATION.md             # This file
```

---

## 4. Database Schema

### Tables

```
company_users
├── id              INT PK AUTO_INCREMENT
├── name            VARCHAR(255)
├── email           VARCHAR(255) UNIQUE
├── password        VARCHAR(255)   -- bcrypt hash
└── company_name    VARCHAR(255)

agents
├── id              INT PK AUTO_INCREMENT
├── company_id      INT FK → company_users.id  (CASCADE DELETE)
├── name            VARCHAR(255)
├── email           VARCHAR(255) UNIQUE
└── password        VARCHAR(255)   -- bcrypt hash

chat_sessions
├── id              INT PK AUTO_INCREMENT
├── user_type       ENUM('company','agent')
├── user_id         INT            -- FK to company_users or agents
├── title           VARCHAR(255)   -- auto-generated from first message
├── created_at      DATETIME
└── updated_at      DATETIME

conversations
├── id              INT PK AUTO_INCREMENT
├── session_id      INT FK → chat_sessions.id  (CASCADE DELETE)
├── user_type       ENUM('company','agent')
├── user_id         INT
├── message         TEXT           -- user's question
├── response        TEXT           -- AI's full response
└── created_at      DATETIME

user_tokens
├── id              INT PK AUTO_INCREMENT
├── user_id         INT
├── user_type       ENUM('company','agent')
├── token           VARCHAR(512) UNIQUE  -- the raw JWT string
├── created_at      DATETIME
└── expires_at      DATETIME
```

### Relationships

```
CompanyUser  ──< Agent            (one company has many agents)
ChatSession  ──< Conversation     (one session has many conversations)
UserToken                         (one row per active login session)
```

> **Note:** `user_id` in `chat_sessions` and `conversations` is a polymorphic integer — it points to either `company_users.id` or `agents.id` depending on `user_type`. There is no hard FK so both tables can share the same column.

---

## 5. Authentication & Session Flow

### Registration (Company only)

```
Browser                    FastAPI                     MySQL
  |                           |                           |
  |-- POST /register -------> |                           |
  |   {name, email, pw,       |-- bcrypt.hash(password)   |
  |    company_name}          |                           |
  |                           |-- INSERT company_users -> |
  |<-- 302 /login?registered  |                           |
```

### Login

```
Browser                    FastAPI                     MySQL
  |                           |                           |
  |-- POST /login ----------> |                           |
  |   {email, password,       |-- SELECT user by email -> |
  |    user_type}             |<- user row                |
  |                           |                           |
  |                           |-- bcrypt.verify()         |
  |                           |                           |
  |                           |-- create_access_token()   |
  |                           |   {user_id, user_type,    |
  |                           |    email, exp}            |
  |                           |                           |
  |                           |-- DELETE expired tokens   |
  |                           |   for this user      ---> |
  |                           |-- INSERT user_tokens  --> |
  |                           |   {user_id, user_type,    |
  |                           |    token, expires_at}     |
  |                           |                           |
  |<-- 302 /*/dashboard ------|                           |
  |    Set-Cookie: access_token=<jwt>; httponly; SameSite=lax
```

### Request Authentication (every protected route)

```
Browser                    FastAPI                     MySQL
  |                           |                           |
  |-- GET /company/dashboard  |                           |
  |   Cookie: access_token=.. |                           |
  |                           |-- read cookie token       |
  |                           |-- decode_token(jwt)       |
  |                           |   verify signature + exp  |
  |                           |                           |
  |                           |-- SELECT user_tokens  --> |
  |                           |   WHERE token=? AND       |
  |                           |   expires_at > NOW()      |
  |                           |<- row found / not found   |
  |                           |                           |
  |                           | [not found] → raise AuthRedirectException
  |<-- 302 /login ------------|                           |
  |                           |                           |
  |                           | [found] → fetch user row  |
  |<-- 200 HTML page  --------|                           |
```

### Logout

```
Browser                    FastAPI                     MySQL
  |                           |                           |
  |-- GET /logout ----------> |                           |
  |   Cookie: access_token=.. |                           |
  |                           |-- DELETE user_tokens  --> |
  |                           |   WHERE token=?           |
  |<-- 302 /login ------------|                           |
  |    Set-Cookie: access_token=; Max-Age=0  (delete)
```

> **Why DB storage?** Storing the token in `user_tokens` allows true server-side revocation. Deleting the row on logout means the JWT is immediately invalid even if the cookie were somehow preserved — the next request fails the DB check.

---

## 6. Application Flow by Role

### Company User Flow

```
Register → Login → /company/dashboard
                        │
              ┌─────────┼──────────────────┐
              ▼         ▼                  ▼
        Stat cards   Manage Agents      Recent convs
        (agents,     /company/agents    (quick view)
         total convs)     │
                    ┌─────┴──────┐
                    ▼            ▼
               Add Agent    Edit/Delete Agent
               (modal)         (modal)

Company user can also navigate to:
  /company/conversations  →  Chat Session list
                                    │
                                    ▼
                          /company/conversations/{id}
                          Single session view
                          (all Q&A pairs in that session)

  /chat/  →  Live AI chat (own sessions only)
```

### Agent Flow

```
Login → /agent/dashboard
              │
    ┌─────────┼──────────────────┐
    ▼         ▼                  ▼
 Stat cards  Recent convs    /agent/conversations
 (own convs  (quick view)    Full history with
  only)                      search + pagination

  /chat/  →  Live AI chat (own sessions only)
```

### Conversation Visibility Rules

| Who sees what | Company User | Agent |
|---|---|---|
| Own chat sessions | ✅ | ✅ |
| Other agents' sessions | ✅ (via /conversations) | ❌ |
| Another company's sessions | ❌ | ❌ |

---

## 7. AI Chat Flow (SSE Streaming)

The chat page (`/chat/`) is a single-page experience driven entirely by JavaScript (`chat.js`). Sessions are loaded and messages are sent without full page reloads.

### Starting a New Chat

```
User clicks "New Chat"
    │
    ├── POST /chat/sessions/new
    │       └── INSERT chat_sessions {title="New Chat"}
    │       └── return {id, title, ...}
    │
    └── JS selects the new session (empty state)
        enables textarea and send button
```

### Sending a Message (SSE Streaming)

```
User types message + hits Enter
    │
    ├── 1. JS appends user bubble to DOM immediately
    ├── 2. JS appends AI bubble with typing animation
    │
    ├── 3. POST /chat/send/stream
    │       Body: {message: "...", session_id: 123}
    │
    │   Server side:
    │   ├── load last 10 conversations for history
    │   ├── open StreamingResponse (text/event-stream)
    │   ├── yield: data: {"session_id": 123}
    │   │
    │   ├── call stream_ai_response(message, history)
    │   │       └── Gemini generate_content_async(stream=True)
    │   │               for each chunk:
    │   │               └── yield: data: {"content": "token..."}
    │   │
    │   └── after all tokens:
    │       ├── INSERT conversations {session_id, message, response}
    │       ├── UPDATE chat_sessions.updated_at
    │       ├── if first message → update title from message text
    │       └── yield: data: {"done": true, "id": conv_id, "title": "..."}
    │
    └── JS SSE reader:
        ├── each {"content"} token → append to AI bubble innerHTML
        ├── {"done"} → update session title in sidebar
        └── re-enable input
```

### Loading an Existing Session

```
User clicks session in sidebar
    │
    ├── GET /chat/sessions/{id}/messages
    │       └── SELECT conversations WHERE session_id=? ORDER BY created_at
    │       └── return {session: {...}, messages: [...]}
    │
    └── JS renders all message pairs in order
        scrolls to bottom
        enables input
```

### Session Management Actions

| Action | Endpoint | Behaviour |
|---|---|---|
| List sessions | `GET /chat/sessions` | Returns sessions sorted by `updated_at` desc |
| New session | `POST /chat/sessions/new` | Creates session with title "New Chat" |
| Delete session | `DELETE /chat/sessions/{id}` | CASCADE deletes all conversations |
| Rename session | `PATCH /chat/sessions/{id}/title` | Updates title (max 100 chars) |
| Load messages | `GET /chat/sessions/{id}/messages` | Returns session + all conversations |

---

## 8. API Endpoints Reference

### Auth  (`/`)

| Method | Path | Description |
|---|---|---|
| GET | `/` or `/login` | Login page |
| POST | `/login` | Authenticate, create DB token, set cookie |
| GET | `/logout` | Delete DB token, clear cookie, redirect |
| GET | `/register` | Registration page |
| POST | `/register` | Create company account |
| GET | `/dashboard` | Smart redirect based on `user_type` in JWT |

### Company  (`/company`)

| Method | Path | Description |
|---|---|---|
| GET | `/company/dashboard` | Company dashboard HTML |
| GET | `/company/agents` | Agent list page |
| POST | `/company/agents/create` | Create a new agent |
| POST | `/company/agents/{id}/update` | Update agent name/email/password |
| POST | `/company/agents/{id}/delete` | Delete agent (cascade deletes sessions) |
| GET | `/company/conversations` | List all chat sessions (company + agents) |
| GET | `/company/conversations/{id}` | View single session's full conversation |

### Agent  (`/agent`)

| Method | Path | Description |
|---|---|---|
| GET | `/agent/dashboard` | Agent dashboard HTML |
| GET | `/agent/conversations` | Agent's own conversation history (paginated, searchable) |

### Chat  (`/chat`)

| Method | Path | Description |
|---|---|---|
| GET | `/chat/` | Chat page HTML (loads sessions via template) |
| GET | `/chat/sessions` | JSON list of user's sessions |
| POST | `/chat/sessions/new` | Create new session, returns JSON |
| GET | `/chat/sessions/{id}/messages` | JSON: session info + all messages |
| DELETE | `/chat/sessions/{id}` | Delete session + all conversations |
| PATCH | `/chat/sessions/{id}/title` | Rename session |
| POST | `/chat/send/stream` | Send message, stream AI response via SSE |

---

## 9. Key Components

### `app/main.py` — Application Factory

- Calls `Base.metadata.create_all()` on startup to auto-create any missing tables.
- Registers all four routers with their prefixes.
- Mounts `/static` for CSS/JS files.
- Registers the `AuthRedirectException` handler — any protected route can raise this and the user is sent to `/login`.
- `/dashboard` reads the JWT from the cookie to decide which dashboard to redirect to.

### `app/auth/dependencies.py` — Auth Guards

Three dependency functions used with `Depends()` in routes:

- **`get_current_company_user`** — requires a valid token + `user_type == "company"`. Returns the `CompanyUser` ORM object.
- **`get_current_agent`** — requires a valid token + `user_type == "agent"`. Returns the `Agent` ORM object.
- **`get_current_user_any`** — accepts either type. Returns `(user_type, user)` tuple. Used by chat routes.

All three call `_extract_payload(request, db)` which:
1. Reads `access_token` from the cookie.
2. Decodes and verifies the JWT signature and expiry.
3. Queries `user_tokens` to confirm the token still exists in the DB (revocation check).

### `app/services/ai_service.py` — Gemini Integration

- `genai.configure()` called at module load with the API key from settings.
- `_build_contents()` converts the stored conversation history into Gemini's `role/parts` format, using `"model"` (not `"assistant"`) for AI turns.
- `stream_ai_response()` is an `async generator` — it yields text tokens as they arrive from Gemini. The `chat.py` route consumes this generator inside its own SSE generator.
- Up to the last 10 exchanges are included as context (to keep token usage bounded).

### `app/routes/chat.py` — SSE Streaming Route

The `send_message_stream` endpoint uses FastAPI's `StreamingResponse` with `media_type="text/event-stream"`. The inner `event_generator()` coroutine:
1. Immediately yields the `session_id` so the browser knows which session was used (important when auto-creating a session).
2. Iterates over the Gemini async generator, yielding each token as an SSE event.
3. After the last token, persists the full response to the DB, updates the session title if it's the first message, and yields a `done` event with the final title.

### `app/static/js/chat.js` — ChatApp Class

The entire chat UI is managed by a single `ChatApp` class instantiated on `DOMContentLoaded`. Key responsibilities:

| Method | Purpose |
|---|---|
| `_newChat()` | POST to create session, prepend to sidebar list, select it |
| `_selectSession(id)` | Fetch messages, render exchange pairs, enable input |
| `_send()` | Read SSE stream, update AI bubble incrementally, finalize title |
| `_appendUserBubble()` | Add user message div to DOM |
| `_appendAIBubble()` | Add AI bubble with typing dots; returns the element for live update |
| `_formatMarkdown()` | Lightweight regex-based markdown → HTML (bold, italic, code, lists, headings) |
| `_toggleSidebar()` | Desktop: toggle `collapsed` class; Mobile: toggle `open` + backdrop |
| `_showToast()` | Inject Bootstrap-styled toast notification |

---

## 10. Configuration Reference

All settings are loaded from `.env` via `pydantic-settings`. Edit `.env` to configure the application.

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_NAME` | `ai_marketing_db` | Database name |
| `DB_USER` | `root` | Database username |
| `DB_PASSWORD` | _(empty)_ | Database password (supports special chars) |
| `JWT_SECRET_KEY` | _(placeholder)_ | **Change in production** — 32+ random chars |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Session length (24 hours) |
| `GEMINI_API_KEY` | _(empty)_ | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `APP_NAME` | `AI Marketing Strategy Assistant` | Displayed in browser title |
| `DEBUG` | `false` | Enables FastAPI debug mode |

> Get a free Gemini API key at https://aistudio.google.com/app/apikey

---

## 11. Frontend Architecture

### Template Inheritance

```
base.html
├── Sidebar (dark nav: brand, nav links, user dropdown)
├── Topbar (hamburger, page title, dark mode, chat button)
└── <main> block  ← each page fills this

  Extends base.html:
  ├── company/dashboard.html
  ├── company/agents.html
  ├── company/conversations.html
  ├── company/session_detail.html
  ├── agent/dashboard.html
  ├── agent/conversations.html

  Standalone (no base):
  └── chat/chat.html     (full-screen layout, custom sidebar)
  └── login.html
  └── register.html
```

### Dark Mode

`main.js` reads `localStorage.getItem('theme')` on load and sets `data-bs-theme="dark"` on `<html>`. Bootstrap 5 responds to this attribute for all component colours. The toggle button switches between `light` and `dark` and persists the choice.

### Responsive Behaviour

- **Desktop (≥ 768px):** The session sidebar is always visible at 270px. The sidebar toggle button collapses it to 0 width with a CSS transition.
- **Mobile (< 768px):** The session sidebar is `position: fixed`, hidden off-screen (`translateX(-100%)`). The toggle slides it in and shows a dark backdrop overlay.

---

## 12. Security Design

| Concern | Implementation |
|---|---|
| Password storage | bcrypt hash via passlib; raw passwords never stored |
| JWT transport | `httponly` cookie (JavaScript cannot read it) |
| CSRF mitigation | `SameSite=lax` cookie attribute |
| Session revocation | Every JWT is stored in `user_tokens`; logout deletes the row; any request against a deleted token is rejected |
| Token expiry | `exp` claim in JWT + `expires_at` column in DB — both enforced |
| DB credentials | `urllib.parse.quote_plus` used for special characters in the connection URL |
| Access isolation | Company users can only see agents/sessions belonging to their `company_id`; agents can only see their own sessions |
| SQL injection | SQLAlchemy ORM parameterised queries used throughout — no raw SQL string concatenation |
| Input length limits | Textarea capped at 4,000 chars; session titles at 100 chars; truncation enforced on both client and server |
