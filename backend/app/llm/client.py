"""Minimal OpenAI-compatible chat client (DeepSeek by default)."""

import asyncio
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


class LlmError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class LlmResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


class LlmClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key.strip()
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> LlmResult:
        if not self.enabled:
            raise LlmError("LLM_NOT_CONFIGURED", "未配置 LLM_API_KEY")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        last_error: Exception | None = None
        started = time.perf_counter()

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 429 or response.status_code >= 500:
                    last_error = LlmError(
                        "LLM_UPSTREAM",
                        f"模型服务暂时不可用（{response.status_code}）",
                        retryable=True,
                    )
                else:
                    response.raise_for_status()
                    data = response.json()
                    choice = data["choices"][0]
                    text = choice["message"]["content"]
                    usage = data.get("usage") or {}
                    return LlmResult(
                        text=text,
                        tokens_in=int(usage.get("prompt_tokens") or 0),
                        tokens_out=int(usage.get("completion_tokens") or 0),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
            except httpx.TimeoutException:
                last_error = LlmError("LLM_TIMEOUT", "模型响应超时", retryable=True)
            except httpx.HTTPStatusError as exc:
                raise LlmError(
                    "LLM_HTTP_ERROR",
                    f"模型请求失败（{exc.response.status_code}）",
                    retryable=False,
                ) from exc
            except httpx.HTTPError as exc:
                last_error = LlmError("LLM_NETWORK", f"模型网络错误：{exc}", retryable=True)

            if attempt < 2:
                await asyncio.sleep(1.2 * (attempt + 1))

        assert last_error is not None
        raise last_error


_client: LlmClient | None = None


def get_llm() -> LlmClient:
    global _client
    if _client is None:
        _client = LlmClient()
    return _client
