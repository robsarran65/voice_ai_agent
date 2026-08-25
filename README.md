# MunAI Voice AI Agent

MunAI Voice AI Agent is a low-cost, configurable voice assistant platform for browser and phone experiences. The current implementation is designed to stay lightweight for demos and pilots while providing a clean path to a multi-tenant SaaS deployment.

The application uses FastAPI, LiteLLM, OpenAI GPT-5 nano as the default low-cost model, Chrome Web Speech APIs for browser speech, and Vapi for phone integration. Tenant behavior is configured through JSON rather than hard-coded customer-specific logic.

> **Current status:** Production-oriented multi-tenant scaffold. The core voice, tenant configuration, cost controls, phone routing, Google integrations, and model telemetry are implemented. Shared persistent state and tenant-scoped OAuth storage are recommended before regulated or high-scale production use.

---

## What changed in the cost-optimized implementation

The current version includes the Sprint 1 P0 and P1 cost improvements:

- **GPT-5 nano is the default LLM** for a fast, low-cost primary path.
- **Per-call telemetry** records model, input tokens, output tokens, cached input tokens, estimated cost, latency, and fallback use.
- **Deterministic fast paths** answer simple greetings, date/time requests, acknowledgements, and similar requests without an LLM call when appropriate.
- **Bounded phone conversation history** prevents Vapi calls from repeatedly sending an ever-growing transcript to the model.
- **Deterministic history compaction** avoids paying a second model simply to summarize old conversation history.
- **Weather responses can bypass the second LLM call** after the tool returns a predictable result.
- **OpenAI prompt caching support** uses a stable tenant-specific cache key and records cached-token usage.
- **Per-tenant output token limits** provide a simple cost-control guardrail.
- **Tenant capability switches** can enable or disable weather, calendar, and email functionality.
- **Tenant-specific trusted caller allowlists** support safer phone routing.
- **Vapi assistant IDs can map directly to tenants.**

---

## Architecture

```text
                         Browser Voice
                  Chrome Web Speech API
                    STT + TTS in browser
                           |
                           v
+----------------------------------------------------------+
|                     FastAPI Backend                      |
|                                                          |
|  /voice-chat/                    /phone/                  |
|       |                              |                    |
|       +------------+-----------------+                    |
|                    v                                      |
|              Tenant Resolution                            |
|        header / request / Vapi assistant ID               |
|                    |                                      |
|                    v                                      |
|             Coordinator Agent                             |
|          / Fast deterministic paths                       |
|                    |                                      |
|          +---------+----------+                           |
|          |                    |                           |
|          v                    v                           |
|     Tool execution       LiteLLM Router                   |
|  Weather/Calendar/Gmail   GPT-5 nano primary              |
|                           configured fallback             |
|                                  |                        |
|                                  v                        |
|                     Token / Cost / Latency telemetry      |
+----------------------------------------------------------+
                           ^
                           |
                     Vapi Phone Channel
```

### Important design choice

Redis, PostgreSQL, pgvector, LangGraph workflows, and retrieval code are **not required by the current runtime**. Historical or experimental implementations are kept under `_archive/` where applicable. They should only be reintroduced when a real product requirement justifies the extra infrastructure and operating cost.

---

## Technology stack

| Layer | Current implementation |
|---|---|
| API | FastAPI |
| Application server | Uvicorn |
| LLM routing | LiteLLM |
| Default LLM | OpenAI GPT-5 nano |
| Browser STT/TTS | Chrome Web Speech API |
| Phone voice | Vapi |
| Weather | Existing weather service integration |
| Calendar | Google Calendar integration |
| Email | Gmail integration |
| Tenant configuration | `config/tenants.json` |
| Runtime telemetry | Token, cached-token, cost, latency, model and fallback logging |
| Language | Python 3.11+ |

---

## Repository structure

```text
voice_ai_agent/
├── api/
│   ├── core/
│   │   ├── coordinator_agent.py   # Main assistant orchestration
│   │   ├── fast_paths.py          # Zero-LLM deterministic responses
│   │   ├── history.py             # Bounded/compacted phone history
│   │   ├── pending.py             # Pending confirmations/session actions
│   │   ├── persona.py             # Tenant-aware assistant persona
│   │   ├── tenant_config.py       # Tenant configuration loader
│   │   └── tools.py               # Tool schemas and execution
│   ├── models/
│   │   ├── request_models.py
│   │   └── response_models.py
│   ├── routes/
│   │   ├── health.py
│   │   ├── phone.py               # Vapi phone webhook path
│   │   └── voice_chat.py          # Browser/API voice chat path
│   ├── services/
│   │   ├── google_auth.py
│   │   ├── google_calendar.py
│   │   ├── google_gmail.py
│   │   ├── litellm_router.py      # Model routing + usage/cost telemetry
│   │   └── weather.py
│   └── index.py                   # FastAPI application entry point
├── config/
│   └── tenants.json               # Multi-tenant configuration
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── assets/
├── scripts/
│   └── google_setup.py
├── _archive/                      # Experimental/future architecture code
├── requirements.txt
├── pyproject.toml
├── start_candy.bat
├── stop_candy.bat
├── ROADMAP.md
└── README.md
```

---

## Tenant configuration

Tenant behavior is managed in:

```text
config/tenants.json
```

Each tenant can configure items such as:

- tenant ID
- assistant name
- company name
- primary model
- fallback model
- maximum output tokens
- model temperature
- phone history window
- phone history compaction size
- monthly LLM budget target
- enabled capabilities
- trusted caller numbers
- Vapi assistant IDs

Example structure:

```json
{
  "default_tenant": "munai-demo",
  "tenants": {
    "munai-demo": {
      "assistant_name": "Candy",
      "company_name": "MunAI Solutions",
      "primary_model": "openai/gpt-5-nano",
      "fallback_model": "deepseek/deepseek-chat",
      "max_output_tokens": 220,
      "temperature": 0.3,
      "capabilities": {
        "weather": true,
        "calendar": true,
        "email": true
      }
    }
  }
}
```

Use the actual fields in the included `config/tenants.json` as the authoritative configuration schema.

### Selecting a tenant

For browser/API traffic, send the tenant header:

```text
X-MunAI-Tenant: munai-demo
```

The `/voice-chat/` request can also include a `tenant_id`.

For Vapi phone traffic, the phone route can resolve a tenant using either:

- `X-MunAI-Tenant`, or
- a Vapi assistant ID mapped in `config/tenants.json`.

### Configuration environment variables

```text
MUNAI_TENANT_CONFIG   Optional path to a different tenant JSON file
MUNAI_DEFAULT_TENANT  Optional default tenant override
```

The tenant loader detects configuration-file changes so common tenant settings can be updated without changing application logic.

---

## Environment variables

Create a `.env` file in the project root. Do **not** commit `.env` or API secrets to GitHub.

Common variables include:

```text
OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
OPENROUTER_API_KEY=...

# Google integrations, when enabled
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Optional tenant configuration overrides
MUNAI_TENANT_CONFIG=config/tenants.json
MUNAI_DEFAULT_TENANT=munai-demo
```

Only configure provider keys that are required by the models and integrations you enable.

---

## Local setup on Windows 11

From PowerShell:

```powershell
cd C:\Users\rober\voice_ai_agent

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Add your local `.env` values, then run the application using the existing launcher:

```powershell
.\start_candy.bat
```

To stop it:

```powershell
.\stop_candy.bat
```

You can also run FastAPI directly if needed:

```powershell
uvicorn api.index:app --reload
```

---

## Browser voice

The browser experience intentionally uses the Chrome Web Speech API for speech-to-text and text-to-speech. This keeps browser speech processing off the paid backend provider path and reduces both latency and operating cost.

The browser sends text requests to the backend and speaks the returned text locally.

---

## Phone voice with Vapi

Vapi handles the phone voice channel and forwards conversation messages to the MunAI phone endpoint.

The cost-optimized phone implementation limits the amount of historical conversation forwarded into each LLM request. Older context is compacted deterministically, while a configurable recent conversation window is retained verbatim.

This is important because forwarding a complete transcript on every turn causes input-token usage to increase as a call gets longer.

---

## LLM cost controls

### Default model

The default low-cost model is configured as:

```text
openai/gpt-5-nano
```

Model selection remains tenant configurable through `config/tenants.json`.

### Deterministic fast paths

Simple requests that do not require model reasoning can be answered directly by application code. This reduces both cost and latency.

### Bounded history

Phone conversations keep a controlled recent-history window rather than continually forwarding an unlimited transcript.

### Tool-response optimization

For tools with predictable output, such as weather, the backend can construct the final user response directly from the tool result rather than making an additional LLM call.

### Prompt caching

For OpenAI calls, a stable tenant-aware prompt cache key is supplied where supported. Telemetry captures cached-input usage so cache effectiveness can be measured.

### Output token limits

Each tenant can define a maximum output token count to prevent unnecessarily long voice responses and unexpected token spend.

---

## Cost and usage telemetry

The LiteLLM routing layer captures available usage information for each model call, including:

- selected model
- input tokens
- output tokens
- cached input tokens
- estimated LLM cost
- call latency
- fallback usage

This creates the foundation for future reporting such as:

```text
Tenant: acme-medical
Channel: phone
Conversation: 8m 14s
LLM calls: 19
Input tokens: 12,408
Cached input tokens: 4,812
Output tokens: 1,322
Estimated LLM cost: $0.0012
Fallbacks: 0
```

A persistent tenant usage ledger is still recommended before enforcing hard monthly budgets.

---

## Google Calendar and Gmail

The project includes Google authentication, Calendar, and Gmail services.

For a single MunAI demo tenant, the current setup can be used as-is with local credentials. Before allowing multiple external customers to connect private Google accounts, implement:

1. tenant-scoped OAuth credentials and token storage,
2. encrypted secret storage,
3. tenant-level authorization checks,
4. audit logging for sensitive actions.

Do not use globally shared Google tokens for unrelated production tenants.

---

## Production readiness

The current codebase is intentionally described as a **production-oriented multi-tenant scaffold**, not a finished regulated production platform.

Before onboarding multiple customers with private data, the next production-hardening priorities are:

1. **Tenant-scoped OAuth/token storage** for Google integrations.
2. **Shared pending/session state** rather than process-local memory when running multiple backend instances.
3. **Persistent usage ledger** for tenant cost reporting and monthly budget enforcement.
4. **Centralized secrets management** for provider and tenant credentials.
5. **Centralized observability and audit logging.**
6. **Authentication and authorization** around tenant administration and customer APIs.
7. **Automated tests and CI/CD quality gates** before deployment.

### Infrastructure we should add only when justified

A future SaaS deployment may use:

- PostgreSQL for tenants, usage records, audit metadata, and OAuth references.
- Redis or another shared short-lived store for session/pending confirmation state.
- A managed secret store for credentials.
- Central logging/metrics for cost, latency, error, and fallback monitoring.

A vector database or RAG pipeline should **not** be added simply because it was part of an earlier architecture concept. Add retrieval infrastructure only when a concrete customer knowledge use case requires it.

---

## Demo vs. production configuration

The same lightweight runtime can support two operating modes:

### Demo / pilot

Use a single tenant with:

- GPT-5 nano
- browser Web Speech
- optional Vapi phone demo
- weather/calendar/email features as needed
- local configuration
- minimal infrastructure

### Multi-tenant SaaS

Use the same core code with:

- one configuration entry per tenant
- tenant-specific assistant branding
- tenant-specific model and token limits
- capability controls
- Vapi assistant mappings
- trusted caller configuration
- persistent tenant usage and OAuth storage as the platform scales

This approach prevents MunAI from paying for production infrastructure before customer volume requires it.

---

## Security notes

- Never commit `.env`, OAuth tokens, provider keys, or tenant secrets.
- Keep write/action tools behind confirmation flows where appropriate.
- Treat phone caller identity as a signal, not strong authentication by itself.
- Validate tenant resolution on every request.
- Keep logs free of unnecessary message content and credentials.
- Use a managed secret store before deploying customer credentials at scale.

---

## Git workflow

Before pushing the cost-optimized implementation:

```powershell
cd C:\Users\rober\voice_ai_agent

git status
git diff
```

Run your local smoke tests and start the assistant. Once validated:

```powershell
git add .
git commit -m "Add cost optimized multi-tenant voice AI architecture"
git push
```

Review `git status` carefully before committing to make sure local credentials, tokens, and temporary files are not staged.

---

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for planned work.

The immediate production priorities are tenant-scoped OAuth, persistent usage accounting, shared session state, centralized secrets, and automated testing/CI.

---

## MunAI Solutions

MunAI Voice AI Agent is being developed as a configurable SaaS foundation for customer-facing voice assistants, business automation, and AI-enabled service workflows.

## Vercel demo capabilities

The Vercel demo is designed to expose three browser capabilities:

- **Weather** — Open-Meteo with wttr.in fallback. No weather API key is required.
- **Live web search** — OpenAI Responses API built-in web search, using `gpt-5-nano` by default.
- **Gmail (read-only)** — list unread/recent email and read a selected message. The demo intentionally cannot send, archive, delete, label, or otherwise modify mail.

### Required Vercel environment variables

Set these under **Vercel Project → Settings → Environment Variables** for Production (and Preview if desired):

```text
OPENAI_API_KEY=...
GOOGLE_TOKEN_JSON_B64=...
```

Optional fallback/search configuration:

```text
OPENROUTER_API_KEY=...
WEB_SEARCH_MODEL=gpt-5-nano
WEB_SEARCH_CALL_COST_USD=0.01
```

Do not commit `.env`, `api/.secrets/token.json`, or Google OAuth client secrets. They are intentionally ignored by Git.

### Put the local Google token into Vercel safely

After `python scripts/google_setup.py` has created `api/.secrets/token.json`, generate a single-line Base64 value in PowerShell:

```powershell
$bytes = [System.IO.File]::ReadAllBytes("api\.secrets\token.json")
[Convert]::ToBase64String($bytes)
```

Copy only the resulting Base64 string into the Vercel environment variable `GOOGLE_TOKEN_JSON_B64`. The authorized-user JSON contains the refresh token needed for serverless cold starts. Treat it as a secret.

After changing Vercel environment variables, redeploy so the new deployment receives them.
