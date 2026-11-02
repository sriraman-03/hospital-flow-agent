"""Optional LLM provider adapter. Returns None when unconfigured or on any failure,
so callers always fall back to the deterministic rule-based output."""
import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an operations assistant for hospital administrators. You receive a JSON object of FACTS retrieved "
    "from the hospital database. Write a concise operational summary using ONLY those facts. Do not invent "
    "numbers, patients, or events. Do not diagnose, recommend treatment, or make clinical or emergency decisions. "
    "Clearly label any suggestion as a recommendation for staff review."
)


def provider_status() -> dict:
    s = get_settings()
    return {"provider": s.llm_provider if s.llm_configured else "none", "configured": s.llm_configured,
            "model": s.llm_model if s.llm_configured else None}


def generate(prompt: str) -> str | None:
    s = get_settings()
    if not s.llm_configured:
        return None
    provider = s.llm_provider.lower()
    try:
        with httpx.Client(timeout=s.llm_timeout_seconds) as client:
            if provider == "anthropic":
                r = client.post(
                    (s.llm_base_url or "https://api.anthropic.com") + "/v1/messages",
                    headers={"x-api-key": s.llm_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": s.llm_model, "max_tokens": 700, "system": SYSTEM_PROMPT,
                          "messages": [{"role": "user", "content": prompt}]},
                )
                r.raise_for_status()
                return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip() or None
            r = client.post(  # OpenAI-compatible
                (s.llm_base_url or "https://api.openai.com/v1") + "/chat/completions",
                headers={"Authorization": f"Bearer {s.llm_api_key}"},
                json={"model": s.llm_model, "max_tokens": 700,
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]},
            )
            r.raise_for_status()
            return (r.json()["choices"][0]["message"]["content"] or "").strip() or None
    except Exception as exc:  # never leak provider errors/keys to clients
        log.warning("LLM call failed: %s", type(exc).__name__)
        return None
