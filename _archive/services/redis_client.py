# ============================================================
# Redis Client (Session Memory)
# Voice AI Agent (Low/No-Cost Edition)
# ============================================================

import os
import redis

# ------------------------------------------------------------
# Environment Variables
# ------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ------------------------------------------------------------
# Redis Client
# ------------------------------------------------------------
try:
    redis_client = redis.Redis.from_url(REDIS_URL)
except Exception as e:
    print(f"Redis connection error: {e}")
    redis_client = None


# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------
def save_session(session_id: str, data: dict, ttl: int = 3600):
    """
    Save conversation/session memory.
    """
    if redis_client:
        redis_client.setex(session_id, ttl, str(data))


def load_session(session_id: str):
    """
    Load conversation/session memory.
    """
    if redis_client:
        value = redis_client.get(session_id)
        if value:
            return value.decode("utf-8")
    return None


def delete_session(session_id: str):
    """
    Delete session memory.
    """
    if redis_client:
        redis_client.delete(session_id)
