"""Zero-cost deterministic responses for simple, safe voice requests."""
import re
from datetime import datetime

_GREETING = re.compile(r"^\s*(hi|hello|hey|good morning|good afternoon|good evening)[!. ]*$", re.I)
_THANKS = re.compile(r"^\s*(thanks|thank you|thanks candy|thank you candy)[!. ]*$", re.I)
_TIME = re.compile(r"\b(what(?:'s| is) the time|what time is it|current time)\b", re.I)
_DATE = re.compile(r"\b(what(?:'s| is) (?:today(?:'s)? date|the date)|what day is it|today(?:'s)? date)\b", re.I)


def deterministic_reply(user_text: str) -> str | None:
    """Return a reply without an LLM when intent is unambiguous."""
    text = (user_text or "").strip()
    if not text:
        return ""
    now = datetime.now().astimezone()
    if _GREETING.fullmatch(text):
        return "Hi, I'm Candy. How can I help?"
    if _THANKS.fullmatch(text):
        return "You're welcome."
    if _TIME.search(text):
        spoken = now.strftime("%I:%M %p").lstrip("0")
        return f"It's {spoken}."
    if _DATE.search(text):
        return f"Today is {now.strftime('%A, %B %d, %Y').replace(' 0', ' ')}."
    return None
