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

# Primary is direct to Anthropic, not through OpenRouter: one fewer network
# hop, and it sidesteps OpenRouter's own account-level rate limiting (a real
# "in-flight budget exhausted" failure hit during latency testing —
# unrelated to this app, but it took the whole demo down with it).
#
# Haiku is primary. Measured back-to-back against Sonnet on this exact
# persona+tools setup: ~1.5s vs ~2.7s per call, and a tool-using question
# costs two calls — so this is roughly the difference between a 3s and a
# 5-6s wait for "what's the weather".
#
# The fallback deliberately goes through OpenRouter rather than staying on
# Anthropic direct. The two failure modes that take down a *direct* provider
# — this account's own Anthropic credit balance running out, or Anthropic
# having an outage — do nothing to OpenRouter, since it's a different
# account and a different path to the model entirely. A same-provider
# fallback would share fate with whatever just failed.
#
# DeepSeek v3, not Sonnet: confirmed (OpenRouter's /models endpoint,
# supported_parameters) to support tool calls, which the fallback needs —
# it runs inside the same weather/calendar/email tool loop as the primary.
# ~10x cheaper than Sonnet per token, so the same OpenRouter balance covers
# far more fallback calls before running out again. No free-tier DeepSeek
# model exists on OpenRouter as of this writing (checked live) — every
# variant carries real, if small, per-token pricing.
CANDY_MODEL = "anthropic/claude-haiku-4-5-20251001"
CANDY_FALLBACK_MODEL = "openrouter/deepseek/deepseek-chat-v3-0324"

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
