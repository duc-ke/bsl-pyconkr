from __future__ import annotations

import json
from datetime import date, datetime
from functools import cached_property
from zoneinfo import ZoneInfo

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    mcp_url: AnyHttpUrl = "http://127.0.0.1:8001/mcp"
    github_token: SecretStr | None = None
    copilot_model: str = "auto"
    allowed_origins: str = ""
    mcp_timeout: float = Field(default=20.0, gt=0)

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, value: str) -> str:
        for origin in cls._parse_origins(value):
            if origin == "*":
                raise ValueError("wildcard CORS origins are not allowed")
            if not origin.startswith(("http://", "https://")):
                raise ValueError("CORS origins must use http or https")
        return value

    @staticmethod
    def _parse_origins(value: str) -> list[str]:
        cleaned = value.strip()
        if not cleaned:
            return []
        if cleaned.startswith("["):
            parsed = json.loads(cleaned)
            if not isinstance(parsed, list) or not all(
                isinstance(item, str) for item in parsed
            ):
                raise ValueError("ALLOWED_ORIGINS must be a JSON string list")
            return [item.strip().rstrip("/") for item in parsed if item.strip()]
        return [
            item.strip().rstrip("/") for item in cleaned.split(",") if item.strip()
        ]

    @cached_property
    def cors_origins(self) -> list[str]:
        return self._parse_origins(self.allowed_origins)

    def copilot_options(self) -> dict[str, object]:
        options: dict[str, object] = {
            "model": self.copilot_model,
            "timeout": 120.0,
        }
        if self.github_token is not None:
            token = self.github_token.get_secret_value()
            if token:
                options["github_token"] = token
        return options


def seoul_today() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()
