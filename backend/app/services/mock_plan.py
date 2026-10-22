"""M0 mock plan stream: fixed skeleton so the frontend can be built before LLM wiring."""

import asyncio
import json
from collections.abc import AsyncIterator

from app.schemas.auth import PlanIn

PHASES: list[tuple[str, str, int, str, list[tuple[str, str]]]] = [
    (
        "p1",
        "基础准备",
        7,
        "跑通最小可运行示例，建立手感",
        [
            ("工具链", "能独立装好环境并跑通 hello world"),
            ("最小示例", "不看文档复现一次并解释每一步"),
        ],
    ),
    (
        "p2",
        "核心概念",
        14,
        "理解核心机制，能用自己的话复述",
        [
            ("核心模型", "画出机制流程并标注关键环节"),
            ("常见术语", "用一句话向新人解释三个术语"),
        ],
    ),
    (
        "p3",
        "动手实践",
        14,
        "完成一个能演示的小项目",
        [
            ("需求拆解", "把需求拆成三个可验证的小任务"),
            ("调试与测试", "为关键路径写至少一个自动化测试"),
        ],
    ),
    (
        "p4",
        "综合验收",
        7,
        "独立讲清楚并复盘",
        [
            ("方案取舍", "说出两个备选方案与选择理由"),
            ("复盘", "列出三个踩坑点与改进项"),
        ],
    ),
]


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_mock_plan(payload: PlanIn) -> AsyncIterator[str]:
    yield sse(
        "meta",
        {
            "stage": "skeleton",
            "goal": payload.goal,
            "daily_minutes": payload.daily_minutes,
            "mock": True,
        },
    )
    await asyncio.sleep(0.15)

    for seq, (pid, title, days, focus, kps) in enumerate(PHASES, start=1):
        yield sse(
            "phase_skeleton",
            {
                "id": pid,
                "seq": seq,
                "title": title,
                "days": days,
                "focus": focus,
                "knowledge_points": [{"name": name, "objective": obj} for name, obj in kps],
            },
        )
        await asyncio.sleep(0.2)

    yield sse(
        "done",
        {
            "plan_id": None,
            "mock": True,
            "hint": "M0 mock：接入 LLM 后这里返回真实 plan_id 并落库",
        },
    )
