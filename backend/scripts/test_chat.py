"""Real smoke for agent chat: chapter question, expect search tool + answer."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

TOKEN = json.loads(Path(r"C:\Users\simple\AppData\Local\Temp\ui-ref\dev-token.json").read_text(encoding="utf-8"))
CHAPTER = "0153c4f7-1867-444e-af33-f5e372910c35"


async def main() -> None:
    payload = {
        "scope": "chapter",
        "context_id": CHAPTER,
        "question": "这一章讲的项目入口，React 的入口文件一般做什么？先搜一下官方文档再回答，给出链接。",
        "history": [],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            "http://127.0.0.1:8000/api/chat/stream",
            json=payload,
            headers={"Authorization": f"Bearer {TOKEN['token']}"},
        ) as resp:
            print("status:", resp.status_code)
            event = ""
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:") and event in {"status", "tool_call", "tool_result", "sources", "answer", "done", "error"}:
                    data = line[5:].strip()
                    print(f"[{event}] {data[:500]}")
                    if event in {"answer", "done", "error"}:
                        event = ""


if __name__ == "__main__":
    asyncio.run(main())
