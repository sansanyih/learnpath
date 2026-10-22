"""Repository ingestion: GitHub -> profile -> chapters -> persistence."""

import asyncio
import json
from string import Template

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.sse import sse
from app.db.database import SessionLocal
from app.db.models import Chapter, Plan, RepoSource, utcnow
from app.llm.client import LlmError, get_llm
from app.llm.json_call import call_json
from app.llm.prompts import load_prompt
from app.llm.repo_schemas import ChapterContentOut, ChapterPlanOut, RepoProfileOut
from app.llm.usage import record_usage
from app.repo.filter import compact_file_list, pick_readme, rank_files
from app.repo.github import GitHubClient, RepoError, parse_repo_url

MAX_FILES = 20
MAX_FILE_CHARS = 5000


async def _load_repo(url: str) -> dict:
    parsed = parse_repo_url(url)
    async with GitHubClient() as gh:
        meta = await gh.repo(parsed.owner, parsed.repo)
        branch = parsed.ref or meta["default_branch"]
        tree = await gh.tree(parsed.owner, parsed.repo, branch)
        blobs = [item for item in tree.get("tree", []) if item.get("type") == "blob"]
        if not blobs:
            raise RepoError("EMPTY_REPO", "这个仓库没有可读的代码文件")

        paths = [item["path"] for item in blobs]
        readme_path = pick_readme(paths)
        readme_text = ""
        if readme_path:
            readme_text = await gh.content(parsed.owner, parsed.repo, readme_path, branch)

        ranked = rank_files(blobs, readme_text)
        if not ranked:
            raise RepoError("NO_LEARNING_FILES", "没有找到适合学习的代码文件")

        contents: dict[str, str] = {}
        semaphore = asyncio.Semaphore(6)

        async def fetch(path: str):
            async with semaphore:
                try:
                    return path, (await gh.content(parsed.owner, parsed.repo, path, branch))[:MAX_FILE_CHARS]
                except Exception:  # noqa: BLE001 - skip unreadable files
                    return path, None

        results = await asyncio.gather(*(fetch(item["path"]) for item in ranked[:MAX_FILES]))
        contents = {path: content for path, content in results if content is not None}

        manifest = ""
        for name in ("requirements.txt", "pyproject.toml", "package.json", "go.mod"):
            if name in contents:
                manifest = contents[name]
                break

        return {
            "owner": parsed.owner,
            "repo": parsed.repo,
            "branch": branch,
            "tree": tree,
            "blobs": blobs,
            "readme": readme_text,
            "ranked": ranked,
            "contents": contents,
            "manifest": manifest,
        }


async def _profile(data: dict, llm):
    system, template = load_prompt("repo_profile_v1.txt")
    user = Template(template).substitute(
        repo_name=f"{data['owner']}/{data['repo']}",
        description="",
        language="",
        readme=data["readme"][:4000],
        file_list=compact_file_list(data["ranked"], 60),
        manifest=data["manifest"][:2500],
    )
    return await call_json(
        purpose="repo_profile",
        system=system,
        user=user,
        schema_cls=RepoProfileOut,
        llm=llm,
        temperature=0.2,
        max_tokens=1500,
    )


async def _chapters(data: dict, profile: RepoProfileOut, llm):
    system, template = load_prompt("chapter_plan_v1.txt")
    user = Template(template).substitute(
        profile_json=json.dumps(profile.model_dump(), ensure_ascii=False),
        file_list=compact_file_list(data["ranked"], 80),
        readme=data["readme"][:3000],
    )
    path_set = {item["path"] for item in data["blobs"]}

    def validate(plan: ChapterPlanOut) -> None:
        for chapter in plan.chapters:
            missing = [path for path in chapter.files if path not in path_set]
            if missing:
                raise ValueError(f"章节「{chapter.title}」引用了不存在的文件：{missing}")

    return await call_json(
        purpose="repo_chapters",
        system=system,
        user=user,
        schema_cls=ChapterPlanOut,
        llm=llm,
        extra_validate=validate,
        temperature=0.4,
        max_tokens=2000,
    )


async def stream_repo_ingest(plan_id: str, user_id: str, url: str):
    yield sse("meta", {"stage": "repo"})
    llm = get_llm()
    if not llm.enabled:
        yield sse("error", {"code": "LLM_NOT_CONFIGURED", "message": "未配置模型 key"})
        return

    try:
        data = await _load_repo(url)
        profile, profile_usages = await _profile(data, llm)
        plan, chapter_usages = await _chapters(data, profile, llm)
    except RepoError as exc:
        yield sse("error", {"code": exc.code, "message": exc.message})
        return
    except LlmError as exc:
        yield sse("error", {"code": exc.code, "message": exc.message})
        return

    async with SessionLocal() as db:
        repo = RepoSource(
            plan_id=plan_id,
            repo_full_name=f"{data['owner']}/{data['repo']}",
            ref=data["branch"],
            commit_sha=str(data["tree"].get("sha", "")),
            profile=profile.model_dump(),
            file_count=len(data["blobs"]),
            status="ready",
            ingested_at=utcnow(),
        )
        db.add(repo)
        await db.flush()

        rows: list[Chapter] = []
        for seq, item in enumerate(plan.chapters, start=1):
            row = Chapter(
                plan_id=plan_id,
                repo_source_id=repo.id,
                seq=seq,
                title=item.title,
                purpose=item.purpose,
                files=item.files,
                concepts=item.concepts,
                status="ready",
            )
            db.add(row)
            await db.flush()
            rows.append(row)

        cost = sum(record_usage(db, user_id, "repo_profile", usage) for usage in profile_usages)
        cost += sum(record_usage(db, user_id, "repo_chapters", usage) for usage in chapter_usages)
        await db.commit()

        repo_id = repo.id
        repo_name = repo.repo_full_name
        ref = repo.ref
        file_count = repo.file_count
        chapters_payload = [
            {
                "id": row.id,
                "seq": row.seq,
                "title": row.title,
                "purpose": row.purpose,
                "files": row.files,
                "concepts": row.concepts,
            }
            for row in rows
        ]

    yield sse(
        "repo_meta",
        {"repo_id": repo_id, "repo": repo_name, "ref": ref, "file_count": file_count},
    )
    yield sse("profile", {"profile": profile.model_dump()})
    for item in chapters_payload:
        yield sse("chapter", item)
    yield sse("done", {"repo_id": repo_id, "chapters": len(chapters_payload), "cost_est": round(cost, 4)})


async def generate_chapter_content(chapter_id: str, user_id: str) -> dict:
    async with SessionLocal() as db:
        chapter = await db.scalar(
            select(Chapter)
            .where(Chapter.id == chapter_id)
            .options(selectinload(Chapter.repo_source))
        )
        if chapter is None:
            raise RepoError("CHAPTER_NOT_FOUND", "章节不存在")

        plan = await db.get(Plan, chapter.plan_id)
        if plan is None:
            raise RepoError("CHAPTER_NOT_FOUND", "章节不存在")
        from app.db.models import Goal

        goal = await db.get(Goal, plan.goal_id)
        if goal is None or goal.user_id != user_id:
            raise RepoError("CHAPTER_NOT_FOUND", "章节不存在")

        if chapter.content_md:
            return {"content_md": chapter.content_md, "cached": True}

        repo = chapter.repo_source
        owner, repo_name = repo.repo_full_name.split("/", 1)
        contents: dict[str, str] = {}
        async with GitHubClient() as gh:
            for path in (chapter.files or [])[:4]:
                try:
                    contents[path] = (await gh.content(owner, repo_name, path, repo.ref))[:6000]
                except Exception:  # noqa: BLE001 - missing file should not block content
                    continue

        llm = get_llm()
        system, template = load_prompt("chapter_content_v1.txt")
        user = Template(template).substitute(
            chapter_json=json.dumps(
                {
                    "title": chapter.title,
                    "purpose": chapter.purpose,
                    "concepts": chapter.concepts,
                    "files": chapter.files,
                },
                ensure_ascii=False,
            ),
            files_json=json.dumps(contents, ensure_ascii=False)[:12000],
            readme=(repo.profile or {}).get("summary", ""),
        )
        content, usages = await call_json(
            purpose="repo_chapter_content",
            system=system,
            user=user,
            schema_cls=ChapterContentOut,
            llm=llm,
            temperature=0.5,
            max_tokens=2500,
        )

        chapter.content_md = content.markdown
        chapter.generated_at = utcnow()
        cost = sum(record_usage(db, user_id, "repo_chapter_content", usage) for usage in usages)
        await db.commit()
        return {"content_md": content.markdown, "cached": False, "cost_est": round(cost, 4)}
