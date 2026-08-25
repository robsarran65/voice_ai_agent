"""Phone transcript compaction to keep per-turn token cost bounded."""
import re


def _clean(value: object, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def compact_phone_history(messages: list[dict], recent_messages: int = 6,
                          summary_chars: int = 700) -> tuple[list[dict], str]:
    """Keep recent turns verbatim and compress older turns without another LLM call."""
    usable = [m for m in messages if m.get("role") in ("user", "assistant")]
    if len(usable) <= recent_messages:
        return usable, ""

    older, recent = usable[:-recent_messages], usable[-recent_messages:]
    parts: list[str] = []
    for msg in older:
        who = "User" if msg.get("role") == "user" else "Candy"
        parts.append(f"{who}: {_clean(msg.get('content'))}")
    summary = " | ".join(parts)
    if len(summary) > summary_chars:
        summary = summary[-summary_chars:]
        first_space = summary.find(" ")
        if first_space > 0:
            summary = "…" + summary[first_space:]
    return recent, summary
