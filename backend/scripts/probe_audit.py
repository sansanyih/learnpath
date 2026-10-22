"""Probe audit aliases and suggestions."""

import json
from pathlib import Path

import httpx

auth = json.loads(Path(r"C:\Users\simple\AppData\Local\Temp\ui-ref\dev-token.json").read_text(encoding="utf-8"))
headers = {"Authorization": f"Bearer {auth['token']}"}
base = "http://127.0.0.1:8000"
plan = auth["plan_id"]
chapter = "0153c4f7-1867-444e-af33-f5e372910c35"

for path, params in [
    ("/api/reviews/due", None),
    ("/api/notes", {"scope": "chapter", "context_id": chapter}),
    (f"/api/plans/{plan}/suggestions", None),
]:
    resp = httpx.get(base + path, headers=headers, params=params, timeout=30)
    print(path, resp.status_code, resp.text[:160])
