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
    "You are {assistant_name}, the voice assistant for {company_name}. "
    "Be warm, sharp, and efficient. Answers are spoken aloud, so keep them "
    "concise and conversational — no markdown, bullet lists, or headers. "
    "Get to the point. Never read raw units like '72F'; say 'seventy-two degrees'. "
    "When a tool gives you a location, name it back so the user can catch a wrong match."
)


def dated_persona(today: str, timezone: str, assistant_name: str = "Candy",
                  company_name: str = "MunAI Solutions") -> str:
    """Build the stable tenant persona plus request-local date context."""
    persona = CANDY_PERSONA.format(
        assistant_name=assistant_name, company_name=company_name
    )
    return (
        f"{persona} Today is {today} and the user's time zone is {timezone}. "
        "Use that whenever a request is relative, like 'tomorrow' or 'next Tuesday'."
    )

# Cost-first default: OpenAI GPT-5 nano. It supports function calling and is
# intended for fast, high-volume work. The fallback stays on a different
# provider so an OpenAI outage/key issue does not take down the demo.
# Both values are environment-overridable for tenant-specific production use.
import os

CANDY_MODEL = os.getenv("CANDY_MODEL", "openai/gpt-5-nano")
CANDY_FALLBACK_MODEL = os.getenv(
    "CANDY_FALLBACK_MODEL", "openrouter/deepseek/deepseek-chat-v3-0324"
)

# Spoken replies get cut off if they run long, and long answers feel wrong
# out loud regardless.
CANDY_MAX_TOKENS = int(os.getenv("CANDY_MAX_TOKENS", "220"))
CANDY_TEMPERATURE = float(os.getenv("CANDY_TEMPERATURE", "0.3"))

# Said out loud when the model call fails. The raw exception must never
# reach this string — Candy reading a stack trace aloud is worse than
# Candy admitting she's stuck.
CANDY_FAILURE_LINE = (
    "Sorry, I couldn't reach my language model just then. Give it another try."
)
