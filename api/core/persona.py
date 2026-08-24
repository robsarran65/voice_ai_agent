# ============================================================
# Candy — domain policy
# ============================================================
# This is the "what this product flow means" layer: who Candy is, which
# model she runs on, and what she says when something breaks. None of it
# belongs in the LLM service, which only knows *how* to call a model.
#
# Keeping it here means a second flow (email drafting, calendar summaries)
# can pass its own persona and model to the same service without editing
# shared code.

CANDY_PERSONA = (
    "You are Candy, a warm, sharp, and efficient voice assistant. "
    "Answers are spoken aloud, so keep them concise and conversational — "
    "no markdown, no bullet lists, no headers. Get to the point. "
    "Never read out raw numbers with units attached like '72F' — say "
    "'seventy-two degrees'. When a tool gives you a location, name it back "
    "so the user can catch a wrong match."
)


def dated_persona(today: str, timezone: str) -> str:
    """
    The persona plus today's date.

    Without this the model has no idea what "tomorrow" or "this afternoon"
    mean, and will either guess a date or ask. Built per request rather than
    stored, so a long-running process can't serve yesterday's date.
    """
    return (
        f"{CANDY_PERSONA} Today is {today} and the user's time zone is "
        f"{timezone}. Use that whenever a request is relative, like "
        f"'tomorrow' or 'next Tuesday'."
    )

# Roadmap item 2: Sonnet is fine for demos, worth costing out before real use.
CANDY_MODEL = "openrouter/anthropic/claude-sonnet-5"
CANDY_FALLBACK_MODEL = "openrouter/mistralai/mistral-large"

# Spoken replies get cut off if they run long, and long answers feel wrong
# out loud regardless.
CANDY_MAX_TOKENS = 300
CANDY_TEMPERATURE = 0.7

# Said out loud when the model call fails. The raw exception must never
# reach this string — Candy reading a stack trace aloud is worse than
# Candy admitting she's stuck.
CANDY_FAILURE_LINE = (
    "Sorry, I couldn't reach my language model just then. Give it another try."
)
