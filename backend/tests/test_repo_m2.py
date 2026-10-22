"""M2 tests: URL parsing, ranking, and repo ingestion persistence (no network)."""

import json

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Chapter, Goal, Plan, RepoSource, User
from app.llm.repo_schemas import ChapterPlanItem, ChapterPlanOut, RepoProfileOut
from app.repo.filter import pick_readme, rank_files
from app.repo.github import RepoError, parse_repo_url
from app.services import repo_service


def test_parse_repo_url_variants():
    assert parse_repo_url("https://github.com/tiangolo/fastapi").owner == "tiangolo"
    assert parse_repo_url("https://github.com/tiangolo/fastapi.git").repo == "fastapi"
    parsed = parse_repo_url("https://github.com/tiangolo/fastapi/tree/master/docs")
    assert parsed.ref == "master"
    assert parse_repo_url("github.com/a/b").repo == "b"


def test_parse_repo_url_rejects_non_github():
    try:
        parse_repo_url("https://gitlab.com/a/b")
    except RepoError as exc:
        assert exc.code == "INVALID_REPO_URL"
    else:
        raise AssertionError("expected RepoError")


def test_rank_files_filters_and_penalizes_tiny_files():
    blobs = [
        {"path": "src/index.ts", "size": 29},
        {"path": "src/core/service.ts", "size": 8000},
        {"path": "node_modules/pkg/index.js", "size": 5000},
        {"path": "requirements.txt", "size": 400},
        {"path": "README.md", "size": 3000},
    ]
    ranked = rank_files(blobs, "see src/core/service.ts")
    paths = [item["path"] for item in ranked]
    assert "node_modules/pkg/index.js" not in paths
    assert paths[0] == "src/core/service.ts"
    assert paths.index("src/index.ts") > paths.index("src/core/service.ts")


def test_pick_readme_prefers_shallow():
    assert pick_readme(["docs/README.md", "README.md"]) == "README.md"
    assert pick_readme(["src/main.py"]) is None


async def test_repo_ingest_persists_chapters(client, monkeypatch):
    async def fake_load(url: str) -> dict:
        return {
            "owner": "acme",
            "repo": "demo",
            "branch": "main",
            "tree": {"sha": "commit-sha"},
            "blobs": [
                {"path": "main.py", "size": 2000},
                {"path": "app.py", "size": 3000},
            ],
            "readme": "# demo",
            "ranked": [
                {"path": "main.py", "size": 2000, "score": 10},
                {"path": "app.py", "size": 3000, "score": 9},
            ],
            "contents": {"main.py": "print(1)"},
            "manifest": "",
        }

    async def fake_profile(data: dict, llm):
        return (
            RepoProfileOut(
                language="Python",
                framework="FastAPI",
                summary="demo repo",
                entrypoints=["main.py"],
                module_map=["app.py → routes"],
                reading_order=["main.py"],
            ),
            [],
        )

    async def fake_chapters(data: dict, profile, llm):
        return (
            ChapterPlanOut(
                chapters=[
                    ChapterPlanItem(
                        title="入口",
                        purpose="理解应用如何启动",
                        files=["main.py"],
                        concepts=["启动", "路由"],
                    ),
                    ChapterPlanItem(
                        title="路由",
                        purpose="理解接口如何注册",
                        files=["app.py"],
                        concepts=["路由", "依赖"],
                    ),
                    ChapterPlanItem(
                        title="配置",
                        purpose="理解配置如何注入",
                        files=["main.py"],
                        concepts=["配置", "环境"],
                    ),
                ]
            ),
            [],
        )

    monkeypatch.setattr(repo_service, "_load_repo", fake_load)
    monkeypatch.setattr(repo_service, "_profile", fake_profile)
    monkeypatch.setattr(repo_service, "_chapters", fake_chapters)
    monkeypatch.setattr(repo_service, "get_llm", lambda: type("L", (), {"enabled": True})())

    async with SessionLocal() as db:
        user = User(email="repo-test@example.com", password_hash="x")
        db.add(user)
        await db.flush()
        goal = Goal(user_id=user.id, title="demo", raw_input="demo", daily_minutes=45, level="beginner")
        db.add(goal)
        await db.flush()
        plan = Plan(goal_id=goal.id, status="ready")
        db.add(plan)
        await db.commit()
        user_id, plan_id = user.id, plan.id

    frames = []
    async for frame in repo_service.stream_repo_ingest(plan_id, user_id, "https://github.com/acme/demo"):
        frames.append(frame)

    body = "".join(frames)
    assert "event: profile" in body
    assert body.count("event: chapter") == 3
    assert "event: done" in body

    async with SessionLocal() as db:
        repos = (await db.scalars(select(RepoSource).where(RepoSource.plan_id == plan_id))).all()
        chapters = (await db.scalars(select(Chapter).where(Chapter.plan_id == plan_id))).all()
        assert len(repos) == 1
        assert len(chapters) == 3
        assert repos[0].commit_sha == "commit-sha"
        assert json.loads(json.dumps(chapters[0].files)) == ["main.py"]
