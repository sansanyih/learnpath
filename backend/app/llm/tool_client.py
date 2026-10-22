"""OpenAI-compatible chat with tool calls (DeepSeek)."""

import asyncio

import httpx

from app.core.config import get_settings
from app.llm.client import LlmError


async def chat_with_tools(messages: list[dict], tools: list[dict]) -> dict:
    settings = get_settings()
    if not settings.llm_enabled:
        raise LlmError("LLM_NOT_CONFIGURED", "未配置模型 key")

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1600,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
    last_error = "模型暂时不可用"

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            last_error = str(exc)[:200]
            await asyncio.sleep(1 + attempt)
            continue

        if response.status_code in {429, 500, 502, 503, 504}:
            last_error = f"模型返回 {response.status_code}"
            await asyncio.sleep(1 + attempt)
            continue
        if response.status_code != 200:
            raise LlmError("LLM_FAILED", f"模型调用失败（{response.status_code}）")
        data = response.json()
        try:
            return data["choices"][0]["message"], data.get("usage", {})
        except (KeyError, IndexError) as exc:
            raise LlmError("LLM_FAILED", "模型返回格式异常") from exc

    raise LlmError("LLM_FAILED", last_error, retryable=True)
