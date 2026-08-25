"""Hot-reloadable JSON tenant configuration for the SaaS edition."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

_CONFIG_PATH = Path(os.getenv(
    "MUNAI_TENANT_CONFIG",
    Path(__file__).resolve().parents[2] / "config" / "tenants.json",
))
_lock = Lock()
_cache: dict = {}
_cache_mtime: float | None = None


@dataclass(frozen=True)
class TenantSettings:
    tenant_id: str
    assistant_name: str = "Candy"
    company_name: str = "MunAI Solutions"
    model: str = "openai/gpt-5-nano"
    fallback_model: str | None = "openrouter/deepseek/deepseek-chat-v3-0324"
    max_tokens: int = 220
    temperature: float = 0.3
    recent_history_messages: int = 6
    history_summary_chars: int = 700
    monthly_llm_budget_usd: float = 25.0
    capabilities: dict[str, bool] = field(default_factory=lambda: {
        "weather": True, "calendar": True, "email": True,
    })
    trusted_callers: tuple[str, ...] = ()
    vapi_assistant_ids: tuple[str, ...] = ()


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load() -> dict:
    global _cache, _cache_mtime
    try:
        mtime = _CONFIG_PATH.stat().st_mtime
    except FileNotFoundError as exc:
        raise RuntimeError(f"Tenant config not found: {_CONFIG_PATH}") from exc
    with _lock:
        if _cache and _cache_mtime == mtime:
            return _cache
        _cache = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        _cache_mtime = mtime
        return _cache


def get_tenant(tenant_id: str | None) -> TenantSettings:
    data = _load()
    tenant_id = (tenant_id or os.getenv("MUNAI_DEFAULT_TENANT", "munai-demo")).strip()
    tenants = data.get("tenants") or {}
    if tenant_id not in tenants:
        raise KeyError(f"Unknown tenant: {tenant_id}")
    values = _merge(data.get("defaults") or {}, tenants[tenant_id] or {})
    return TenantSettings(
        tenant_id=tenant_id,
        assistant_name=str(values.get("assistant_name") or "Candy"),
        company_name=str(values.get("company_name") or "MunAI Solutions"),
        model=str(values.get("model") or "openai/gpt-5-nano"),
        fallback_model=values.get("fallback_model"),
        max_tokens=max(32, min(int(values.get("max_tokens", 220)), 1000)),
        temperature=float(values.get("temperature", 0.3)),
        recent_history_messages=max(2, min(int(values.get("recent_history_messages", 6)), 20)),
        history_summary_chars=max(200, min(int(values.get("history_summary_chars", 700)), 3000)),
        monthly_llm_budget_usd=max(0.0, float(values.get("monthly_llm_budget_usd", 25.0))),
        capabilities={k: bool(v) for k, v in (values.get("capabilities") or {}).items()},
        trusted_callers=tuple(str(v) for v in values.get("trusted_callers") or []),
        vapi_assistant_ids=tuple(str(v) for v in values.get("vapi_assistant_ids") or []),
    )


def tenant_for_vapi_assistant(assistant_id: str | None) -> TenantSettings:
    if assistant_id:
        data = _load()
        for tenant_id in (data.get("tenants") or {}):
            settings = get_tenant(tenant_id)
            if assistant_id in settings.vapi_assistant_ids:
                return settings
    return get_tenant(None)
