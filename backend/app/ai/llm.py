from typing import Any

import httpx

from app.config import get_settings


class LlmError(Exception):
    pass


def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, temperature: float = 0.1) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_enabled:
        raise LlmError("LLM no configurado")
    payload: dict[str, Any] = {"model": settings.llm_model, "messages": messages, "temperature": temperature}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise LlmError(str(exc)) from exc
