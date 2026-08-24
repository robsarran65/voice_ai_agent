# 🎙️ Voice AI Agent — SaaS Platform

> A production-ready, multi-agent Voice AI SaaS built with FastAPI, LangGraph, LiteLLM, and a Chrome-native STT/TTS frontend. Orchestrate specialist AI agents over a real-time voice interface, backed by Redis, PostgreSQL, and a retrieval pipeline — deployable to Vercel in minutes.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Local Setup](#local-setup)
- [Local Testing](#local-testing)
- [API Reference](#api-reference)
- [Deployment to Vercel](#deployment-to-vercel)
- [Contributing](#contributing)
- [License](#license)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (Frontend)                        │
│         Chrome Web Speech API — STT / TTS                        │
│         Sends text to /api/voice-chat · Speaks response back     │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTPS / JSON
┌───────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend (Python)                       │
│  ┌──────────────┐   ┌──────────────────────────────────────────┐ │
│  │ /health      │   │ /api/voice-chat                          │ │
│  │ (liveness)   │   │  → CoordinatorAgent                      │ │
│  └──────────────┘   │      → DAG / LangGraph Workflow           │ │
│                     │          → Specialist Agents              │ │
│                     │      → LiteLLM Router (model dispatch)    │ │
│                     │      → Retrieval Pipeline (RAG)           │ │
│                     └──────────────────────────────────────────┘ │
│  ┌──────────────────────┐   ┌─────────────────────────────────┐  │
│  │ Redis Client         │   │ PostgreSQL Client                │  │
│  │ (session / cache)    │   │ (users, history, embeddings)     │  │
│  └──────────────────────┘   └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Orchestration

```
CoordinatorAgent
    │
    ├── LangGraph DAG
    │       ├── Node: Intent Classification
    │       ├── Node: Context Retrieval  (Retrieval Pipeline → Postgres pgvector)
    │       ├── Node: Specialist Dispatch
    │       │       ├── Specialist Agent A  (e.g., FAQ / Knowledge)
    │       │       ├── Specialist Agent B  (e.g., Task / Action)
    │       │       └── Specialist Agent N  (extensible)
    │       └── Node: Response Synthesis
    │
    └── LiteLLM Router
            ├── Primary model   (e.g., GPT-4o)
            └── Fallback model  (e.g., Claude 3.5 Sonnet)
```

**Key design decisions:**
- **CoordinatorAgent** is the single entry-point for all voice turns; it owns session state and routes work through the DAG.
- **LangGraph** defines the agent DAG as code — nodes are pure Python functions, edges encode conditional branching.
- **LiteLLM** provides a unified interface across OpenAI, Anthropic, Cohere, and others — swap models without touching agent logic.
- **Redis** stores ephemeral session context (conversation window, user prefs) for sub-millisecond reads.
- **PostgreSQL + pgvector** persists conversation history and document embeddings for the retrieval pipeline.
- **Chrome STT/TTS** keeps audio processing client-side — no audio bytes leave the browser, reducing latency and cost.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + Uvicorn |
| Agent orchestration | LangGraph (DAG), custom CoordinatorAgent |
| LLM routing | LiteLLM |
| Cache / session | Redis |
| Database | PostgreSQL + pgvector |
| Retrieval (RAG) | Custom retrieval pipeline (chunking → embed → pgvector search) |
| Frontend | Vanilla JS + Chrome Web Speech API (STT / TTS) |
| Deployment | Vercel (Serverless Functions / Edge) |
| Language | Python 3.11+ |

---

## Folder Structure

```
voice_ai_agent/
│
├── api/                          # FastAPI application
│   ├── main.py                   # App factory, mounts routers, CORS, lifespan
│   ├── routes/
│   │   ├── voice_chat.py         # POST /api/voice-chat  — main voice turn
│   │   └── health.py             # GET  /health          — liveness probe
│   ├── agents/
│   │   ├── coordinator.py        # CoordinatorAgent — session mgmt, DAG entry
│   │   ├── specialists/
│   │   │   ├── base.py           # BaseSpecialistAgent ABC
│   │   │   ├── knowledge.py      # FAQ / knowledge-base specialist
│   │   │   └── task.py           # Action / task-execution specialist
│   │   └── dag/
│   │       ├── graph.py          # LangGraph StateGraph definition
│   │       └── nodes.py          # Individual DAG node functions
│   ├── llm/
│   │   └── router.py             # LiteLLM router config (models, fallbacks)
│   ├── retrieval/
│   │   ├── pipeline.py           # Chunking → embedding → pgvector search
│   │   └── embedder.py           # Embedding model wrapper
│   ├── db/
│   │   ├── postgres.py           # AsyncPG / SQLAlchemy client + pool
│   │   └── redis.py              # Redis async client + session helpers
│   └── schemas/
│       └── voice.py              # Pydantic models (VoiceChatRequest/Response)
│
├── frontend/
│   ├── index.html                # Single-page app shell
│   ├── app.js                    # Chrome STT + TTS + fetch to /api/voice-chat
│   └── style.css                 # Minimal UI styles
│
├── scripts/
│   ├── seed_db.py                # Seed Postgres schema + sample embeddings
│   └── ingest.py                 # Ingest documents into retrieval pipeline
│
├── tests/
│   ├── test_voice_chat.py        # Route integration tests (pytest + httpx)
│   ├── test_coordinator.py       # CoordinatorAgent unit tests
│   ├── test_dag.py               # LangGraph DAG node tests
│   └── conftest.py               # Fixtures (test app, mock Redis/Postgres)
│
├── vercel.json                   # Vercel routing + serverless function config
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
├── Makefile                      # Dev shortcuts
└── README.md
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Use `pyenv` or system install |
| Node.js | 18+ | For Vercel CLI only |
| Redis | 7+ | Local install or Redis Cloud free tier |
| PostgreSQL | 15+ with pgvector | `CREATE EXTENSION vector;` required |
| Vercel CLI | latest | `npm i -g vercel` |
| Chrome browser | any recent | Required for Web Speech API (STT/TTS) |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values before running.

```bash
cp .env.example .env
```

| Variable | Description | Example |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key for LiteLLM primary model | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic key for fallback model | `sk-ant-...` |
| `LITELLM_MODEL_PRIMARY` | Primary LLM model name | `gpt-4o` |
| `LITELLM_MODEL_FALLBACK` | Fallback LLM model name | `claude-3-5-sonnet-20241022` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `DATABASE_URL` | Postgres async connection string | `postgresql+asyncpg://user:pass@localhost:5432/voiceai` |
| `EMBEDDING_MODEL` | Embedding model for retrieval | `text-embedding-3-small` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000,https://yourdomain.vercel.app` |
| `SECRET_KEY` | App secret for signing tokens | random 32-char string |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## Local Setup

### 1 — Clone the repository

```bash
git clone https://github.com/your-org/voice_ai_agent.git
cd voice_ai_agent
```

### 2 — Create and activate a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4 — Start Redis (local)

```bash
# macOS (Homebrew)
brew services start redis

# Windows (WSL or Docker)
docker run -d -p 6379:6379 redis:7-alpine

# Verify
redis-cli ping   # → PONG
```

### 5 — Start PostgreSQL and enable pgvector

```bash
# macOS (Homebrew)
brew services start postgresql@15

# Connect and create database
psql postgres -c "CREATE DATABASE voiceai;"
psql voiceai  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 6 — Configure environment variables

```bash
cp .env.example .env
# Edit .env with your API keys and connection strings
```

### 7 — Seed the database

```bash
python scripts/seed_db.py
```

### 8 — (Optional) Ingest documents into the retrieval pipeline

```bash
python scripts/ingest.py --source ./docs/
```

### 9 — Start the FastAPI server

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now live at `http://localhost:8000`.  
Open `frontend/index.html` in **Chrome** to start a voice session.

> **Tip:** Use the `Makefile` shortcut: `make dev`

---

## Local Testing

### Run the full test suite

```bash
pytest tests/ -v
```

### Run with coverage

```bash
pytest tests/ --cov=api --cov-report=term-missing
```

### Test individual layers

```bash
# Route integration tests only
pytest tests/test_voice_chat.py -v

# Agent unit tests
pytest tests/test_coordinator.py tests/test_dag.py -v
```

### Manual API test (curl)

```bash
curl -X POST http://localhost:8000/api/voice-chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "text": "Hello, what can you help me with?"}'
```

**Expected response:**
```json
{
  "session_id": "test-123",
  "response": "Hi! I can help you with ...",
  "agent": "knowledge",
  "latency_ms": 412
}
```

### Health check

```bash
curl http://localhost:8000/health
# → {"status": "ok", "redis": "ok", "postgres": "ok"}
```

### Swagger UI

Interactive API docs available at:
```
http://localhost:8000/docs
```

---

## API Reference

### `POST /api/voice-chat`

Send a transcribed voice turn and receive an AI-generated response.

**Request body:**
```json
{
  "session_id": "string",   // UUID; create once per browser session
  "text": "string"          // STT transcript from Chrome Web Speech API
}
```

**Response:**
```json
{
  "session_id": "string",
  "response": "string",     // Text to pass to Chrome TTS
  "agent": "string",        // Which specialist handled the turn
  "latency_ms": 0           // End-to-end server latency
}
```

| Status | Meaning |
|---|---|
| `200` | Successful agent response |
| `422` | Validation error (missing fields) |
| `500` | Internal server / LLM error |

---

### `GET /health`

Liveness probe for Vercel and uptime monitors.

**Response:**
```json
{
  "status": "ok",
  "redis": "ok",
  "postgres": "ok"
}
```

---

## Deployment to Vercel

### 1 — Install Vercel CLI

```bash
npm install -g vercel
```

### 2 — Login to Vercel

```bash
vercel login
```

### 3 — Review `vercel.json`

The included `vercel.json` maps all backend routes to the FastAPI serverless function and serves the frontend statically:

```json
{
  "version": 2,
  "builds": [
    { "src": "api/main.py", "use": "@vercel/python" },
    { "src": "frontend/**", "use": "@vercel/static" }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "api/main.py" },
    { "src": "/health",   "dest": "api/main.py" },
    { "src": "/(.*)",     "dest": "frontend/$1"  }
  ]
}
```

### 4 — Set production environment variables

```bash
vercel env add OPENAI_API_KEY
vercel env add ANTHROPIC_API_KEY
vercel env add REDIS_URL
vercel env add DATABASE_URL
vercel env add EMBEDDING_MODEL
vercel env add CORS_ORIGINS
vercel env add SECRET_KEY
vercel env add LOG_LEVEL
```

> Use **Vercel's dashboard → Settings → Environment Variables** as an alternative to the CLI.

### 5 — Deploy to preview

```bash
vercel
```

Vercel returns a preview URL. Test it fully before promoting to production.

### 6 — Deploy to production

```bash
vercel --prod
```

### 7 — Post-deployment checks

```bash
# Health check
curl https://your-project.vercel.app/health

# Voice chat smoke test
curl -X POST https://your-project.vercel.app/api/voice-chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "smoke-001", "text": "Are you online?"}'
```

### Vercel Deployment Notes

- **Serverless cold starts:** FastAPI initializes the LangGraph DAG and DB pool on first invocation. Warm-up latency is ~1–2 s. Use Vercel's **Fluid Compute** or keep-alive pings if sub-second cold starts are required.
- **Redis:** Use Redis Cloud or Upstash (Vercel Marketplace) — local Redis is not reachable from Vercel Functions.
- **PostgreSQL:** Use Neon, Supabase, or any cloud Postgres with pgvector support. Vercel Postgres (powered by Neon) is the easiest integration.
- **Timeout:** Default Vercel Function timeout is 10 s. LLM calls can exceed this — set `"maxDuration": 30` in `vercel.json` for the `/api/voice-chat` function if needed.
- **CORS:** Set `CORS_ORIGINS` to your Vercel production URL to prevent browser blocks.

---

## Contributing

1. Fork the repository and create a feature branch: `git checkout -b feat/your-feature`
2. Write tests for any new agent nodes or routes.
3. Ensure `pytest tests/ -v` passes with no failures.
4. Run `ruff check . && ruff format .` before committing.
5. Open a pull request with a clear description of the change.

---

## License

MIT © 2026 Robert — see [LICENSE](LICENSE) for details.
