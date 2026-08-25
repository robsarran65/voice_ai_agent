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
   - **Two routing bugs fixed since, still unverified on Vercel itself:** the catch-all
     `/(.*)` sent *every* path to `index.html`, so `app.js`, `style.css` and `/assets/*`
     would all have been served HTML; and `"src": "/voice-chat"` could not match the
     `/voice-chat/` the frontend actually posts to. Both corrected in `vercel.json`, but
     nobody has deployed it yet — treat this item as open until someone does.
4. **Email/calendar capabilities — built for single-user, still not multi-tenant.**
   Modelled on jarvis-2's `gcal.py`/`gmail.py`/`google_auth.py`, including its key lesson:
   never force a scope list when *loading* a token, since a refresh token can only be
   redeemed for the scopes it was granted with.
   - Candy keeps its **own** `api/.secrets/token.json` — sharing jarvis-2's would mean
     writing to that project on every refresh, and it's reference-only.
   - Scopes are `calendar.events` + **`gmail.readonly`**. Jarvis 2 holds `gmail.modify`
     because it sends and archives; Candy only reads. A token that cannot write is the
     main limit on what a prompt-injected email can achieve.
   - Calendar writes are staged in `api/core/pending.py` and require a spoken yes. The
     yes/no decision is made in plain code, not by the model.
   - **Still open for SaaS:** the desktop OAuth flow and the in-memory pending store are
     both single-user. Multi-tenant needs a web consent flow with per-tenant token storage,
     and `gmail.readonly` is a *restricted* scope requiring Google app verification before
     anyone outside your own test users can grant it.
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
7. ~~**No customer branding/theming yet.**~~ **Resolved.** `frontend/style.css` now carries
   the MunAI identity — every colour in it was sampled out of `frontend/assets/munai-logo.jpg`
   and `munai-banner.jpg`, so the page is made of the same brushed metal, navy linework and
   teal circuitry as the mark. To rebrand for another client, edit only the `--brand-*` block
   at the top of the stylesheet and swap the two files in `frontend/assets/`; nothing below
   that block hardcodes a brand colour.
8. **Phone number — built, not activated.** `api/routes/phone.py` is Vapi's "custom LLM"
   adapter: Vapi owns the phone number, call audio, STT and TTS, and POSTs a plain HTTP
   request per turn (OpenAI `/chat/completions` shape) that this endpoint answers using the
   same `CoordinatorAgent` the browser uses. No persistent connection on our side — this is
   why Vapi and not a raw telephony provider (Telnyx/Twilio + a WebSocket audio bridge):
   those need a held-open connection, which doesn't run on Vercel. Vapi's own docs publish a
   Vercel serverless example of this exact pattern; Retell (the other batteries-included
   option checked) explicitly rules out serverless in its own docs.
   - **Ships fully dormant.** `VAPI_SERVER_SECRET` and `CANDY_ALLOWED_CALLERS` in `.env` are
     both blank. Unset secret → every request gets 401, regardless of anything else. Empty
     allowlist → nobody is trusted, so calendar/email stay hidden even once authorized —
     weather still answers for anyone, since it isn't sensitive.
   - **Caller-ID allowlist, not a lock.** `CANDY_ALLOWED_CALLERS` is a comma-separated list of
     E.164 numbers permitted to use calendar/email over the phone. Caller ID can be spoofed —
     this is a deterrent matching the demo's current low-stakes use, not a real access control.
     A PIN/passphrase gate would be the next step up if this becomes more than a personal demo.
   - **Verified without any real Vapi account or spend** — every case below was a simulated
     HTTP POST shaped like Vapi's documented request: dormant-by-default (401 with both vars
     unset), wrong/missing secret (401), both accepted auth header styles succeed, an
     untrusted caller's calendar question gets a natural deflection with the tool never
     offered, an allowlisted caller gets a real calendar answer, and a two-turn exchange
     confirmed `history` actually carries prior turns (Candy recalled a fact stated one turn
     earlier) rather than being accepted and silently ignored.
   - **One real unknown, flagged rather than guessed past:** Vapi's own docs disagree with
     themselves on where the caller's number lives in the payload — their Call-object schema
     says `customer.number`, their own spam-call-rejection example reads `from.phoneNumber`.
     `_extract_caller_number()` in `phone.py` tries both. Confirm which one (or both) a real
     call actually sends during activation and simplify once known.
   - **To activate:** create a Vapi account (pay-as-you-go, a few dollars covers real testing —
     no large free credit, unlike the DIY telephony route that was considered and passed over
     for the Vercel-compatibility reason above), set the assistant's Custom LLM URL to
     `<public-url>/phone/chat/completions`, set that same secret as `VAPI_SERVER_SECRET`, add
     trusted numbers to `CANDY_ALLOWED_CALLERS`, buy a number in Vapi, place a real call.
   - **Does not fix item 1** (mobile/Bluetooth browser STT) — that's Candy's existing *web* UI
     failing to capture speech in the browser; this is a wholly separate phone number people
     dial directly. Real phone audio does need server-side STT/TTS same as item 1's proposed
     fix would, but Vapi supplies that itself here, so item 1 remains open and unrelated.

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
