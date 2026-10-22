"""Plan horizon: parse goal duration and normalize phase days."""

from app.llm.schemas import PhaseSkeletonIn, SkeletonOut
from app.services.plan_service import _available_days, _normalize_days, _parse_horizon_days


def test_parse_horizon_from_goal_text():
    assert _parse_horizon_days("三个月掌握python") == 90
    assert _parse_horizon_days("3个月掌握 FastAPI") == 90
    assert _parse_horizon_days("6周入门前端") == 42
    assert _parse_horizon_days("90天拿下算法") == 90
    assert _parse_horizon_days("半年掌握后端") == 180
    assert _parse_horizon_days("掌握 Python") is None


def test_available_days_uses_goal_when_no_deadline():
    assert _available_days(None, "三个月掌握python") == 90
    assert _available_days(None, "随便学学") == 42


def _phase(index: int, days: int) -> PhaseSkeletonIn:
    return PhaseSkeletonIn(
        id=f"p{index}",
        title=f"阶段 {index}",
        days=days,
        focus="focus",
        prerequisites=[] if index == 1 else [f"p{index - 1}"],
        knowledge_points=[
            {"name": f"kp {index}-{j}", "objective": "o"} for j in range(1, 4)
        ],
        deliverable="d",
    )


def test_normalize_days_matches_three_month_goal():
    skeleton = SkeletonOut(phases=[_phase(1, 6), _phase(2, 7), _phase(3, 8), _phase(4, 8), _phase(5, 7)])
    normalized = _normalize_days(skeleton, 90)
    assert sum(phase.days for phase in normalized.phases) == 90
