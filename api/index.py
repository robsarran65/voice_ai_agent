from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
async def root():
    """
    This API does not serve the frontend UI locally (only Vercel's
    routing does that). Run `frontend/index.html` through its own
    static server and point it at this API instead.
    """
    return {
        "message": "This is the Voice AI Agent API, not the UI.",
        "endpoints": ["/health/", "/voice-chat/", "/phone/chat/completions"],
        "frontend": "Serve frontend/index.html with its own static server.",
    }


# ------------------------------------------------------------
# Vercel requires a handler named "app"
# ------------------------------------------------------------
# Nothing else needed — Vercel will import this file
