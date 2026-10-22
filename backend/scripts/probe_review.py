"""Probe review, mastery and chapter progress APIs."""

import json
from pathlib import Path

import httpx

auth = json.loads(Path(r"C:\Users\simple\AppData\Local\Temp\ui-ref\dev-token.json").read_text(encoding="utf-8"))
headers = {"Authorization": f"Bearer {auth['token']}"}
base = "http://127.0.0.1:8000"

for path in ["/api/review/queue", "/api/mastery"]:
    resp = httpx.get(base + path, headers=headers, timeout=30)
    print(path, resp.status_code, resp.text[:300])

chapter = "0153c4f7-1867-444e-af33-f5e372910c35"
resp = httpx.put(
    f"{base}/api/chapters/{chapter}/progress", headers=headers, json={"status": "learning"}, timeout=30
)
print("put", resp.status_code, resp.text[:120])
resp = httpx.get(f"{base}/api/chapters/{chapter}/progress", headers=headers, timeout=30)
print("get", resp.status_code, resp.text[:120])
