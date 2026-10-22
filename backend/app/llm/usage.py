"""Token usage accounting shared by generation pipelines."""

from app.core.config import get_settings
from app.db.models import LlmUsage
from app.llm.client import LlmResult


def record_usage(db, user_id: str | None, purpose: str, result: LlmResult) -> float:
    settings = get_settings()
    cost = (
        result.tokens_in / 1000 * settings.llm_price_in_per_1k
        + result.tokens_out / 1000 * settings.llm_price_out_per_1k
    )
    db.add(
        LlmUsage(
            user_id=user_id,
            purpose=purpose,
            model=settings.llm_model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_est=round(cost, 6),
            latency_ms=result.latency_ms,
            ok=True,
        )
    )
    return cost
