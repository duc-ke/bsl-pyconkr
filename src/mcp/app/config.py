from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(Path(__file__).resolve().parent),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    neis_api_key: SecretStr = SecretStr("sample")
    neis_base_url: str | None = None
    neis_connect_timeout: float = Field(default=3.0, gt=0)
    neis_read_timeout: float = Field(default=10.0, gt=0)

    def api_key(self) -> str:
        return self.neis_api_key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
