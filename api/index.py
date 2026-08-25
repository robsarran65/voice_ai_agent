import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes.health import router as health_router
from api.routes.phone import router as phone_router
from api.routes.voice_chat import router as voice_chat_router

# Safe below the imports now: the LLM service reads OPENROUTER_API_KEY per
# call rather than at import time, so nothing has consumed it yet.
load_dotenv()

app = FastAPI()

# ------------------------------------------------------------
# CORS (allow your Vercel frontend + local dev)
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------
app.include_router(voice_chat_router, prefix="/voice-chat")
app.include_router(health_router, prefix="/health")
# Dormant until VAPI_SERVER_SECRET is set — see api/routes/phone.py.
app.include_router(phone_router, prefix="/phone")

# ------------------------------------------------------------
# FRONTEND
# ------------------------------------------------------------
# Vercel's current model is one Python function for the whole app — there's
# no separate static-build step to hand frontend/ to anymore (the previous
# vercel.json did that via the now-deprecated "builds"/"@vercel/static"
# config). Mounted last, so it only catches requests the routers above
# didn't already claim; html=True serves index.html for "/".
#
# An absolute path, not "frontend": Vercel's function runtime's working
# directory isn't guaranteed to be the repo root, so a relative path here
# would be a bug that only shows up in production.
_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")

# ------------------------------------------------------------
# Vercel requires a handler named "app"
# ------------------------------------------------------------
# Nothing else needed — Vercel will import this file (see pyproject.toml's
# [tool.vercel] entrypoint, since api/index.py isn't one of Vercel's
# default-detected entrypoint locations).
