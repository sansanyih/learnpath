"""On-demand task learning guide (cached per task)."""

from string import Template

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Goal, Phase, Plan, Task, TaskGuide
from app.llm.client import LlmError, get_llm
from app.llm.guide_schemas import TaskGuideOut
from app.llm.json_call import call_json
from app.llm.prompts import load_prompt
from app.llm.usage import record_usage


class GuideError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _fallback(task: Task, phase: Phase) -> dict:
    return {
        "steps": [
            f"先用 10 分钟读一遍和「{task.title}」相关的官方文档，记下 3 个关键词。",
            "照着最小示例手敲一遍，不要复制粘贴，逐行解释它在做什么。",
            f"按验收标准自测：{task.acceptance or '能独立复现并讲清楚每一步'}。",
        ],
        "concepts": [
            {
                "name": task.title,
                "explanation": f"这是「{phase.title}」里要掌握的核心动作，先弄清楚输入、输出和失败情况。",
            },
            {
                "name": "验收标准",
                "explanation": task.acceptance or "能独立复现，并用自己的话讲清楚每一步为什么这样做。",
            },
        ],
        "code_examples": [],
        "materials": [
            {"title": f"搜索：{task.title}", "url": "", "kind": "search"},
        ],
        "search_queries": [task.title, f"{phase.title} 教程 入门"],
        "self_check": [
            "不看资料，能否复述关键步骤？",
            "遇到报错时，能否定位到具体环节并说明原因？",
        ],
        "pitfalls": ["只看不写，缺少肌肉记忆", "跳过验收标准，误以为已经会了"],
    }


async def get_or_create_task_guide(task_id: str, user_id: str) -> dict:
    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
        phase = await db.get(Phase, task.phase_id) if task else None
        plan = await db.get(Plan, phase.plan_id) if phase else None
        goal = await db.get(Goal, plan.goal_id) if plan else None
        if task is None or phase is None or plan is None or goal is None or goal.user_id != user_id:
            raise GuideError("TASK_NOT_FOUND", "任务不存在", 404)

        existing = await db.scalar(select(TaskGuide).where(TaskGuide.task_id == task_id))
        if (
            existing is not None
            and existing.payload
            and "concepts" in existing.payload
            and "code_examples" in existing.payload
        ):
            return existing.payload

        system, template = load_prompt("task_guide_v2.txt")
        user = Template(template).substitute(
            goal=goal.title,
            phase=phase.title,
            focus=phase.focus,
            title=task.title,
            type=task.type,
            minutes=task.duration_min,
            acceptance=task.acceptance,
            level=goal.level,
        )
        try:
            out, usages = await call_json(
                purpose="task_guide",
                system=system,
                user=user,
                schema_cls=TaskGuideOut,
                llm=get_llm(),
                temperature=0.4,
                max_tokens=1800,
            )
            payload = out.model_dump()
            for usage in usages:
                record_usage(db, user_id, "task_guide", usage)
        except LlmError:
            # 不缓存兜底内容：下次打开重新尝试，避免一次坏输出永久占位
            return _fallback(task, phase)

        if existing is not None:
            existing.payload = payload
        else:
            db.add(TaskGuide(task_id=task_id, user_id=user_id, payload=payload))
        await db.commit()
        return payload
