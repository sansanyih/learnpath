"""Probe stats, demo, export after P1."""

import json
from pathlib import Path

import httpx

auth = json.loads(Path(r"C:\Users\simple\AppData\Local\Temp\ui-ref\dev-token.json").read_text(encoding="utf-8"))
headers = {"Authorization": f"Bearer {auth['token']}"}
base = "http://127.0.0.1:8000"

demo = httpx.get(f"{base}/api/demo/plan", timeout=30)
print("demo", demo.status_code, len(demo.json().get("phases", [])))

stats = httpx.get(f"{base}/api/stats", headers=headers, timeout=30)
print("stats", stats.status_code, stats.json().get("streak"), stats.json().get("week"))
print("strategy", stats.json().get("review_strategy"))

export = httpx.get(f"{base}/api/me/export", headers=headers, timeout=30)
print("export", export.status_code, list(export.json().keys())[:6])
