"""Probe DuckDuckGo HTML search and DeepSeek function calling."""

import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402


async def ddg() -> None:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        resp = await client.get("https://html.duckduckgo.com/html/", params={"q": "FastAPI Depends 用法"})
    print("DDG status:", resp.status_code, "len:", len(resp.text))
    print(resp.text[:200].replace("\n", " "))
    links = re.findall(r'class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', resp.text)
    print("links:", len(links))
    for href, title in links[:3]:
        print("-", re.sub(r"<.*?>", "", title)[:60], "|", href[:100])


async def deepseek_tools() -> None:
    settings = get_settings()
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": "你是助手，需要时调用工具。"},
            {"role": "user", "content": "搜索一下 FastAPI Depends 的官方文档，然后一句话总结。"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "搜索互联网",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
    print("LLM status:", resp.status_code)
    data = resp.json()
    message = data["choices"][0]["message"]
    print("tool_calls:", json.dumps(message.get("tool_calls"), ensure_ascii=False)[:500])
    print("content:", (message.get("content") or "")[:200])


async def main() -> None:
    await ddg()
    await deepseek_tools()


if __name__ == "__main__":
    asyncio.run(main())
