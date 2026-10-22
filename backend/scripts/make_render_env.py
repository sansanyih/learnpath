"""Generate a Render-ready .env.render from backend/.env + Neon URL.

Usage:
  python scripts/make_render_env.py "postgresql+asyncpg://.../neondb?ssl=require"
Does not print secret values.
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / "backend" / ".env"
OUT = ROOT / ".env.render"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: make_render_env.py <DATABASE_URL>")
    database_url = sys.argv[1]
    env = parse_env(ENV_FILE)
    lines = [
        "APP_NAME=学径 LearnPath API",
        f"DATABASE_URL={database_url}",
        f"JWT_SECRET={secrets.token_hex(32)}",
        "JWT_ALGORITHM=HS256",
        "TOKEN_EXPIRE_DAYS=7",
        "CORS_ORIGINS=https://learnpath.onrender.com",
        "LLM_BASE_URL=" + env.get("LLM_BASE_URL", "https://api.deepseek.com"),
        "LLM_API_KEY=" + env.get("LLM_API_KEY", ""),
        "LLM_MODEL=" + env.get("LLM_MODEL", "deepseek-chat"),
        "LLM_TIMEOUT_SECONDS=90",
        "LLM_PRICE_IN_PER_1K=0.001",
        "LLM_PRICE_OUT_PER_1K=0.002",
        "GUEST_DAILY_LIMIT=5",
        "USER_DAILY_TOKEN_LIMIT=50000",
        "AGENT_MAX_ROUNDS=3",
        "AGENT_DAILY_LIMIT=20",
        "TAVILY_API_KEY=" + env.get("TAVILY_API_KEY", ""),
        "GITHUB_TOKEN=" + env.get("GITHUB_TOKEN", ""),
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written {OUT} keys={len(lines)} (values not printed)")


if __name__ == "__main__":
    main()
