"""Probe chapter quiz, latest attempt, chat history and annotations."""

import json
from pathlib import Path

import httpx

auth = json.loads(Path(r"C:\Users\simple\AppData\Local\Temp\ui-ref\dev-token.json").read_text(encoding="utf-8"))
headers = {"Authorization": f"Bearer {auth['token']}"}
base = "http://127.0.0.1:8000"
chapter = "0153c4f7-1867-444e-af33-f5e372910c35"

quiz = httpx.post(f"{base}/api/chapters/{chapter}/quiz", headers=headers, timeout=120).json()
print("quiz questions:", len(quiz.get("questions", [])))
answers = []
for item in quiz.get("questions", []):
    answers.append({"quiz_id": item["id"], "answer": "A" if item["type"] == "choice" else "我的回答：先讲结论，再解释原因。"})
result = httpx.post(
    f"{base}/api/chapters/chapter-quiz/submit",
    headers=headers,
    json={"chapter_id": chapter, "answers": answers},
    timeout=120,
).json()
print("quiz result:", result.get("score"), result.get("status"))

latest = httpx.get(f"{base}/api/chapters/{chapter}/quiz/latest", headers=headers, timeout=30).json()
print("latest:", latest.get("score"), len(latest.get("results", [])))

note = httpx.post(
    f"{base}/api/annotations",
    headers=headers,
    json={"scope": "chapter", "context_id": chapter, "content": "测试批注：先看 README 再看入口。"},
    timeout=30,
).json()
print("annotation:", note)
notes = httpx.get(
    f"{base}/api/annotations", headers=headers, params={"scope": "chapter", "context_id": chapter}, timeout=30
).json()
print("annotations:", len(notes.get("items", [])))

history = httpx.get(
    f"{base}/api/chat/history", headers=headers, params={"scope": "chapter", "context_id": chapter}, timeout=30
).json()
print("history items:", len(history.get("items", [])))
