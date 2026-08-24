from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    """
    Simple health check endpoint for Vercel and local debugging.
    Returns a basic JSON payload confirming the API is running.
    """
    return {"status": "ok", "message": "Voice AI Agent backend is running."}
