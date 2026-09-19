from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "attendance"
    use_mock_db: bool = False

    session_secret: str = "dev-only-change-me-in-production"
    session_cookie_name: str = "session"
    session_max_age_seconds: int = 60 * 60 * 12

    rp_id: str = "localhost"
    rp_name: str = "출퇴근·급여 관리"
    origin: str = "http://localhost:5173"

    device_code_ttl_minutes: int = 10
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
