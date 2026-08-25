# ============================================================
# Web search — OpenAI Responses API built-in web search
# ============================================================
import logging
import os
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)
RESPONSES_URL = "https://api.openai.com/v1/responses"
TIMEOUT_S = 25.0


@dataclass(frozen=True)
class WebSearchResult:
    ok: bool
    answer: str = ""
    sources: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error: str | None = None


def is_ready() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def search(query: str) -> WebSearchResult:
    query = (query or "").strip()
    if not query:
        return WebSearchResult(ok=False, error="empty query")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return WebSearchResult(ok=False, error="OPENAI_API_KEY is not set")

    payload = {
        "model": os.getenv("WEB_SEARCH_MODEL", "gpt-5-nano"),
        "input": query,
        "tools": [{"type": "web_search"}],
        "include": ["web_search_call.action.sources"],
        "max_output_tokens": 220,
        "store": False,
    }
    try:
        r = httpx.post(
            RESPONSES_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=TIMEOUT_S,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.warning("OpenAI web search failed: %s", exc)
        return WebSearchResult(ok=False, error=str(exc))

    answer_parts: list[str] = []
    sources: list[dict] = []
    for item in data.get("output", []) or []:
        if item.get("type") == "message":
            for content in item.get("content", []) or []:
                if content.get("type") == "output_text" and content.get("text"):
                    answer_parts.append(content["text"])
                    for ann in content.get("annotations", []) or []:
                        if ann.get("type") == "url_citation":
                            sources.append({"title": ann.get("title", ""), "url": ann.get("url", "")})
        if item.get("type") == "web_search_call":
            for src in ((item.get("action") or {}).get("sources") or []):
                url = src.get("url")
                if url:
                    sources.append({"title": src.get("title", ""), "url": url})

    # Deduplicate source URLs while preserving order.
    seen = set()
    unique = []
    for src in sources:
        if src.get("url") and src["url"] not in seen:
            seen.add(src["url"])
            unique.append(src)

    usage = data.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    # Search tool is currently $0.01/call. Keep it configurable so pricing can
    # be changed without a code deploy. Token estimate uses GPT-5 nano rates.
    call_cost = float(os.getenv("WEB_SEARCH_CALL_COST_USD", "0.01"))
    token_cost = input_tokens * 0.05 / 1_000_000 + output_tokens * 0.40 / 1_000_000
    answer = " ".join(answer_parts).strip()
    if not answer:
        return WebSearchResult(ok=False, error="web search returned no text")
    return WebSearchResult(
        ok=True,
        answer=answer,
        sources=unique[:5],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=call_cost + token_cost,
    )
