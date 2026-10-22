"""Shared JSON-mode call with validation and repair loop."""

import json
import re

from app.llm.client import LlmError, LlmResult


def extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


async def call_json(
    *,
    purpose: str,
    system: str,
    user: str,
    schema_cls,
    llm,
    extra_validate=None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> tuple[object, list[LlmResult]]:
    last_error = ""
    usages: list[LlmResult] = []
    for _attempt in range(3):
        prompt = user if not last_error else f"{user}\n\n上一次输出不合法：{last_error}\n请修正后只输出 JSON。"
        result = await llm.chat_json(system, prompt, temperature=temperature, max_tokens=max_tokens)
        usages.append(result)
        try:
            data = json.loads(extract_json(result.text))
            obj = schema_cls.model_validate(data)
            if extra_validate is not None:
                extra_validate(obj)
            return obj, usages
        except Exception as exc:  # noqa: BLE001 - surfaced through the repair loop
            last_error = str(exc)[:500]

    raise LlmError("INVALID_OUTPUT", f"模型输出不合法：{last_error}")
