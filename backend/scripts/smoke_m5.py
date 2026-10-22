"""End-to-end smoke against a running backend. Prints PASS/FAIL per feature."""

import json
import sys
import time
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

BASE = "http://127.0.0.1:8000"
EMAIL = f"m5smoke{int(time.time())}@example.com"
PASSWORD = "password123"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        detail = fn()
        RESULTS.append((name, True, detail or ""))
        print(f"PASS {name} {detail or ''}")
        return detail
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False, str(exc)[:200]))
        print(f"FAIL {name}: {str(exc)[:200]}")
        return None


def sse(client: httpx.Client, path: str, payload: dict, headers: dict) -> tuple[str, list[dict]]:
    events: list[dict] = []
    body = ""
    with client.stream("POST", BASE + path, json=payload, headers=headers, timeout=180) as resp:
        if resp.status_code != 200:
            raise AssertionError(f"{path} HTTP {resp.status_code}: {resp.read()[:200]}")
        event = ""
        for line in resp.iter_lines():
            body += line + "\n"
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
                try:
                    events.append({"event": event, "data": json.loads(data)})
                except json.JSONDecodeError:
                    pass
    return body, events


def main() -> None:
    client = httpx.Client(timeout=60)
    check("health", lambda: client.get(BASE + "/health").json()["status"])

    def register_login():
        reg = client.post(BASE + "/api/auth/register", json={"email": EMAIL, "password": PASSWORD})
        assert reg.status_code == 201, reg.text
        login = client.post(BASE + "/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert login.status_code == 200, login.text
        return login.json()

    auth = check("register/login", register_login)
    if not auth:
        return
    headers = {"Authorization": f"Bearer {auth['token']}"}
    user_id = auth["user"]["id"]

    check("me", lambda: client.get(BASE + "/api/me", headers=headers).json()["email"])

    plan_id = None

    def gen_plan():
        nonlocal plan_id
        body, events = sse(
            client,
            "/api/plans/stream",
            {"goal": "三个月掌握 Python 基础", "daily_minutes": 45, "level": "beginner"},
            headers,
        )
        assert "event: phase_skeleton" in body
        assert "event: phase_detail" in body
        done = [e for e in events if e["event"] == "done"]
        assert done and done[0]["data"].get("plan_id"), body[-400:]
        plan_id = done[0]["data"]["plan_id"]
        return f"plan={plan_id[:8]} fallback={done[0]['data'].get('fallback_phases')}"

    check("plan generation", gen_plan)

    detail = None

    def plan_consistency():
        nonlocal detail
        detail = client.get(f"{BASE}/api/plans/{plan_id}", headers=headers).json()
        days = sum(phase["days"] for phase in detail["phases"])
        tasks = sum(len(phase["tasks"]) for phase in detail["phases"])
        assert days == 90, days
        for phase in detail["phases"]:
            assert len(phase["tasks"]) == phase["days"], (phase["seq"], phase["days"], len(phase["tasks"]))
            offsets = sorted(t["day_offset"] for t in phase["tasks"])
            assert offsets == list(range(phase["days"])), (phase["seq"], offsets)
            assert all(t["duration_min"] <= 45 for t in phase["tasks"])
        return f"days={days} tasks={tasks} phases={len(detail['phases'])}"

    check("plan days/tasks coverage", plan_consistency)

    first_phase = detail["phases"][0]
    first_task = first_phase["tasks"][0]

    def task_guide():
        resp = client.post(f"{BASE}/api/tasks/{first_task['id']}/guide", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["steps"] and data["concepts"] is not None
        return f"steps={len(data['steps'])} concepts={len(data.get('concepts', []))}"

    check("task guide", task_guide)

    def task_toggle():
        resp = client.patch(f"{BASE}/api/tasks/{first_task['id']}", json={"status": "done"}, headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()["phase_status"]

    check("task toggle", task_toggle)

    def phase_quiz():
        quiz = client.post(
            f"{BASE}/api/plans/{plan_id}/phases/{first_phase['id']}/quiz", headers=headers
        )
        assert quiz.status_code == 200, quiz.text
        questions = quiz.json()["questions"]
        assert len(questions) == 5
        answers = [
            {"quiz_id": q["id"], "answer": "A" if q["type"] == "choice" else "先讲结论，再解释原因。"}
            for q in questions
        ]
        result = client.post(
            f"{BASE}/api/quizzes/submit",
            json={"phase_id": first_phase["id"], "answers": answers},
            headers=headers,
        )
        assert result.status_code == 200, result.text
        data = result.json()
        return f"score={data['score']} adjustment={data['adjustment']['action'] if data['adjustment'] else None}"

    check("phase quiz + grading", phase_quiz)

    repo_id = None
    chapter_id = None

    def repo_import():
        nonlocal repo_id, chapter_id
        body, events = sse(
            client,
            f"/api/plans/{plan_id}/repos/stream",
            {"url": "https://github.com/bnufw/lear_by_ai"},
            headers,
        )
        chapters = [e for e in events if e["event"] == "chapter"]
        assert len(chapters) >= 3, body[-400:]
        repos = client.get(f"{BASE}/api/plans/{plan_id}/repos", headers=headers).json()
        repo_id = repos[0]["id"]
        chapter_id = repos[0]["chapters"][0]["id"]
        return f"chapters={len(chapters)}"

    check("repo import", repo_import)

    def chapter_read():
        chapter = client.get(f"{BASE}/api/chapters/{chapter_id}", headers=headers)
        assert chapter.status_code == 200, chapter.text
        content = client.post(f"{BASE}/api/chapters/{chapter_id}/content", headers=headers, timeout=120)
        assert content.status_code == 200, content.text
        files = client.get(f"{BASE}/api/chapters/{chapter_id}/files", headers=headers, timeout=60)
        assert files.status_code == 200 and files.json()["files"], files.text
        return f"content={len(content.json()['content_md'])} files={len(files.json()['files'])}"

    check("chapter content/files", chapter_read)

    def chapter_quiz():
        quiz = client.post(f"{BASE}/api/chapters/{chapter_id}/quiz", headers=headers, timeout=120)
        assert quiz.status_code == 200, quiz.text
        questions = quiz.json()["questions"]
        assert len(questions) == 5
        answers = [
            {"quiz_id": q["id"], "answer": "A" if q["type"] == "choice" else "我的回答"}
            for q in questions
        ]
        result = client.post(
            f"{BASE}/api/chapters/chapter-quiz/submit",
            json={"chapter_id": chapter_id, "answers": answers},
            headers=headers,
            timeout=120,
        )
        assert result.status_code == 200, result.text
        latest = client.get(f"{BASE}/api/chapters/{chapter_id}/quiz/latest", headers=headers).json()
        return f"score={result.json()['score']} latest={latest['score']}"

    check("chapter quiz + latest", chapter_quiz)

    def chapter_status():
        put = client.put(
            f"{BASE}/api/chapters/{chapter_id}/progress",
            json={"status": "learning"},
            headers=headers,
        )
        assert put.status_code == 200 and put.json()["status"] == "learning"
        get = client.get(f"{BASE}/api/chapters/{chapter_id}/progress", headers=headers)
        assert get.json()["status"] == "learning"
        return "learning"

    check("chapter status", chapter_status)

    def chat():
        body, events = sse(
            client,
            "/api/chat/stream",
            {
                "scope": "chapter",
                "context_id": chapter_id,
                "question": "这一章先看哪个文件？一句话回答。",
                "history": [],
            },
            headers,
        )
        answer = [e for e in events if e["event"] == "answer"]
        assert answer and answer[0]["data"]["content"], body[-400:]
        history = client.get(
            f"{BASE}/api/chat/history",
            params={"scope": "chapter", "context_id": chapter_id},
            headers=headers,
        ).json()["items"]
        assert len(history) >= 2
        note = client.post(
            f"{BASE}/api/annotations",
            json={"scope": "chapter", "context_id": chapter_id, "content": "smoke 批注"},
            headers=headers,
        )
        assert note.status_code == 200
        return f"history={len(history)} answer={len(answer[0]['data']['content'])}"

    check("agent chat + history + annotation", chat)

    def stats_review():
        stats = client.get(f"{BASE}/api/stats", headers=headers).json()
        assert stats["review_strategy"]["intervals"] == [1, 3, 7, 15, 30]
        queue = client.get(f"{BASE}/api/reviews/due", headers=headers).json()
        mastery = client.get(f"{BASE}/api/mastery", headers=headers).json()
        return f"queue={queue['total']} mastery={len(mastery['items'])}"

    check("stats + review + mastery", stats_review)

    check("demo plan", lambda: f"phases={len(client.get(BASE + '/api/demo/plan').json()['phases'])}" if True else "")

    def export():
        data = client.get(f"{BASE}/api/me/export", headers=headers).json()
        assert data["user"]["email"] == EMAIL
        return f"keys={len(data)}"

    check("account export", export)

    def delete_plan():
        resp = client.delete(f"{BASE}/api/plans/{plan_id}", headers=headers)
        assert resp.status_code == 204, resp.text
        assert client.get(f"{BASE}/api/plans/{plan_id}", headers=headers).status_code == 404
        return "204"

    check("plan delete cascade", delete_plan)

    def delete_account():
        resp = client.delete(BASE + "/api/me", headers=headers)
        assert resp.status_code == 200, resp.text
        relogin = client.post(BASE + "/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert relogin.status_code == 200
        return "soft-deleted + recovered"

    check("account delete/recover", delete_account)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\nRESULT {passed}/{len(RESULTS)} passed")
    print(f"SMOKE_EMAIL={EMAIL}")
    print(f"SMOKE_USER_ID={user_id}")
    failed = [name for name, ok, _ in RESULTS if not ok]
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
