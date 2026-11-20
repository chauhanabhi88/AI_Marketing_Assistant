# AI Marketing Strategy Chat Application

A production-ready web application that lets **Company Users** manage **Agents**, and both can chat with a local AI assistant (via [Ollama](https://ollama.com)) for marketing strategy advice.

## Tech Stack

| Layer        | Technology                    |
|--------------|-------------------------------|
| Backend      | FastAPI (Python 3.12+)        |
| Frontend     | Jinja2 + Bootstrap 5          |
| Database     | MySQL 8                       |
| ORM          | SQLAlchemy 2                  |
| Auth         | JWT (httponly cookie) + bcrypt|
| AI           | Ollama (local LLM)            |
| Containers   | Docker + Docker Compose       |

---

## Project Structure

```
app/
├── main.py            # FastAPI entry point
├── config.py          # Settings (pydantic-settings + .env)
├── database.py        # SQLAlchemy engine & session
├── models/            # ORM models (CompanyUser, Agent, Conversation)
├── schemas/           # Pydantic request/response schemas
├── routes/            # Route handlers (auth, company, agent, chat)
├── services/          # AI service (Ollama streaming)
├── auth/              # JWT handler + FastAPI dependencies
├── utils/
├── templates/         # Jinja2 HTML templates (Bootstrap 5)
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── company/       # dashboard, agents, conversations
│   ├── agent/         # dashboard, conversations
│   └── chat/          # chat.html (ChatGPT-style UI)
└── static/
    ├── css/style.css
    └── js/            # main.js (dark mode, sidebar) + chat.js
```

---

## Quick Start (Local)

### 1. Prerequisites

- Python 3.12+
- MySQL 8
- [Ollama](https://ollama.com/download) running locally

### 2. Clone & configure

```bash
git clone <repo-url>
cd sample

# Copy and edit the env file
cp .env.example .env
```

Edit `.env` with your MySQL credentials and preferred Ollama model.

### 3. MySQL setup

```sql
CREATE DATABASE ai_marketing_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Or run the provided schema directly:

```bash
mysql -u root -p < schema.sql
```

### 4. Ollama setup

```bash
# Install Ollama then pull a model
ollama pull mistral        # ~4 GB
# or
ollama pull phi3           # ~2.3 GB — faster
# or
ollama pull llama3         # ~4.7 GB

ollama serve               # starts on http://localhost:11434
```

Set `OLLAMA_MODEL=mistral` (or whichever you pulled) in `.env`.

### 5. Install dependencies & run

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload --port 9000
```

Open [http://localhost:8000](http://localhost:9000).

### 6. Create your first Company account

Go to [http://localhost:8000/register](http://localhost:9000/register) and create a Company User account. Then log in and add Agents from the dashboard.

---

## Docker Compose

```bash
cp .env.example .env        # edit DB_PASSWORD and DB_NAME

docker compose up --build
```

Services:
- **app** → [http://localhost:9000](http://localhost:9000)
- **mysql** → port 3306

---

## User Roles

### Company User
- Register at `/register`
- Dashboard: stats, recent conversations
- Manage Agents: create / edit / delete
- View **all** conversations (own + agents')
- Chat with AI

### Agent
- Created by a Company User
- Dashboard: personal stats
- Chat with AI
- View **own** conversations only

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/login` | Sign in (form) |
| GET/POST | `/register` | Company registration |
| GET | `/logout` | Invalidate session |
| GET | `/company/dashboard` | Company dashboard |
| GET | `/company/agents` | List agents |
| POST | `/company/agents/create` | Create agent |
| POST | `/company/agents/{id}/update` | Update agent |
| POST | `/company/agents/{id}/delete` | Delete agent |
| GET | `/company/conversations` | All conversations (search + paginate) |
| GET | `/agent/dashboard` | Agent dashboard |
| GET | `/agent/conversations` | Agent's own conversations |
| GET | `/chat/` | Chat page |
| POST | `/chat/send` | Send message (non-streaming) |
| POST | `/chat/send/stream` | Send message (SSE streaming) |
| DELETE | `/chat/conversations/{id}` | Delete a conversation |

---

## Features

- **Streaming AI responses** — tokens appear word-by-word (SSE)
- **Dark mode** — toggle in top bar, persisted in localStorage
- **Sidebar** — collapsible; mobile-friendly overlay
- **Markdown rendering** — AI responses render bold, lists, code blocks
- **Typing animation** — three-dot indicator while waiting
- **Conversation history** — paginated, searchable
- **Role-based access** — company users and agents see different menus
- **Secure auth** — JWT in httponly cookie, bcrypt passwords

---

## Security Notes

- JWT stored in `httponly; SameSite=lax` cookie — not accessible to JavaScript
- All passwords hashed with bcrypt (cost factor 12)
- Role guards on every protected route
- Never commit `.env` — use `.env.example` as a template
- For production: use HTTPS, set `secure=True` on cookies, rotate `JWT_SECRET_KEY`
