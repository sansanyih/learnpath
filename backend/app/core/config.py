"""Application settings loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "学径 LearnPath API"
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    token_expire_days: int = 7
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 90
    llm_price_in_per_1k: float = 0.001
    llm_price_out_per_1k: float = 0.002
    github_token: str = ""
    tavily_api_key: str = ""

    guest_daily_limit: int = 5
    agent_max_rounds: int = 3
    agent_daily_limit: int = 20
    user_daily_token_limit: int = 50000

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
