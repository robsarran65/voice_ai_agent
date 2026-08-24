# Candy — Voice AI Assistant SaaS: Roadmap & Known Issues

Working notes for picking this back up. Candy is a browser-based voice assistant demo
(FastAPI + OpenRouter LLM + Chrome STT/TTS), intended to go from demo → sellable
client product with email/calendar capabilities, modeled in part on `C:\Users\rober\jarvis-2`
(review-only reference, never edited directly).

## Current state (working)

- Full pipeline: mic → Chrome STT → FastAPI backend → OpenRouter (`claude-sonnet-5`) → spoken reply
- Candy persona (system prompt) + consistent pinned TTS voice + TTS cold-start fix
- `.gitignore` in place, `requirements.txt` accurate for what's currently imported
- Confirmed working end-to-end on desktop Chrome with a wired mic/headphones

## Known issues / deferred items

1. **Mobile + Bluetooth STT is broken, no JS-side fix exists.** Confirmed by direct testing:
   a Bluetooth mic reliably drops the first ~2 words of every utterance, and no cue-delay
   (tried up to 2.5s) or `getUserMedia` pre-warming fixes it — root cause is OS/Bluetooth-stack
   profile negotiation latency, not something fixable from the page. Separately, **iOS Safari
   doesn't support `webkitSpeechRecognition` at all** — the app doesn't work on iPhone,
   period. Since most real users will be on phone + Bluetooth, this blocks a real product
   launch (demo-only for now is fine).
   - **Real fix (not started):** replace browser STT with `MediaRecorder` + a continuous
     rolling audio pre-buffer + server-side transcription (Whisper / Deepgram / AssemblyAI).
     Works cross-platform including iOS, and structurally avoids the Bluetooth drop since
     audio is already buffered before any negotiation lag matters.
2. **Default LLM model isn't cheap.** Currently `anthropic/claude-sonnet-5` via OpenRouter —
   fine for occasional demos, expensive if the client runs this a lot. Worth evaluating a
   cheaper/faster default (e.g. a Haiku-tier or free-tier OpenRouter model) before real use.
3. **Vercel deployment is unverified.** `vercel.json` routes both the FastAPI backend and the
   static frontend, but this hasn't been tested end-to-end on Vercel yet — in particular
   whether `frontend/app.js`'s `BACKEND_URL` logic (localhost vs. relative path) actually
   resolves correctly once both are served from one Vercel domain, and whether the FastAPI
   app works as a Vercel Python serverless function as currently structured.
4. **Email/calendar capabilities not started.** Client wants this eventually, modeled on
   jarvis-2's `gcal.py`/`gmail.py`/`google_auth.py`. Jarvis 2 uses a **desktop, one-time-setup
   OAuth flow** (run a script once, get a local `token.json`) — that does **not** map directly
   onto a multi-tenant Vercel SaaS. Will need a proper web OAuth flow (per-client/tenant
   consent + token storage) instead of porting jarvis-2's flow as-is.
5. ~~**`CoordinatorAgent` is a shared singleton.**~~ **Resolved.** It still is a
   module-level instance, but it no longer holds per-request state: `respond()` is
   stateless and `run_next_task()` now takes its `completed` set as an explicit
   parameter instead of mutating `self.completed`. Sharing it across concurrent
   requests is safe.
6. **Two divergent Python environments on this dev machine** (Anaconda vs. standalone
   `py -3.13`) can silently disagree on installed packages — already bit us once
   (`litellm`/`python-dotenv` missing from whichever env `uvicorn` actually resolves to).
   A project-local virtualenv would remove this whole class of bug before it matters for
   deployment.
7. **No customer branding/theming yet.** Need a `style.css` for the frontend so the demo
   (and eventually per-client deployments) can be white-labeled/branded instead of using
   unstyled default HTML.

## Service-layer pass (done)

Applied the two-layer split — actions own domain rules, services own reusable
mechanics:

- `api/core/persona.py` (new) holds Candy's persona, model choice, generation
  params, and failure line. These were hardcoded inside the LLM service, so a
  second flow could not have used it without editing shared code.
- `api/services/litellm_router.py` now takes every input explicitly and returns
  a structured `LLMResult(ok, text, model, error)`. It previously returned the
  error *string* as if it were the reply — Candy read exceptions aloud.
- `CoordinatorAgent.respond()` owns failure classification: real detail to the
  logs, a speakable line to the user.
- Dead scaffolding moved to `_archive/` (see `_archive/README.md`) — five service
  modules with no callers, four of which could not even be imported, plus a
  second divergent copy of `TASK_GRAPH`.

The rebuild below is still the target shape. Per the migration checklist, grow
into it one caller at a time rather than building all the layers up front —
that is what produced the archived scaffolding.

## Next build plan (target structure, in dependency order)

Restructuring from the current flat `api/core` / `api/services` layout into this shape,
building bottom-up so each layer only depends on what's already built:

1. `requirements.txt` + `api/schemas/voice.py` — foundation, no dependencies
2. `api/db/postgres.py` + `api/db/redis.py` — data layer
3. `api/llm/router.py` — LLM wiring
4. `api/retrieval/embedder.py` + `pipeline.py` — RAG pipeline
5. `api/agents/dag/nodes.py` + `graph.py` — DAG logic
6. `api/agents/specialists/*` + `coordinator.py` — agent layer
7. `api/routes/*` + `api/main.py` — wire everything together
8. `frontend/*` — voice UI (+ `style.css` for customer branding, see above)
9. `scripts/*` — seed + ingest
10. `tests/*` — test coverage
11. `vercel.json` + `Makefile` — deploy config

## Before pushing to GitHub

- Double check `git status` once the repo is initialized — confirm `.env` and any
  `__pycache__` directories are excluded (`.gitignore` already covers both)
- Revisit item 3 above (Vercel deploy verification) before or right after the first push
