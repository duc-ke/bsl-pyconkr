import json
from functools import cached_property

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    neis_base_url: AnyHttpUrl = "https://open.neis.go.kr"
    neis_api_key: SecretStr | None = None
    allowed_origins: str = ""
    neis_connect_timeout: float = Field(default=3.0, gt=0)
    neis_read_timeout: float = Field(default=10.0, gt=0)

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

    def api_key(self) -> str:
        if self.neis_api_key is None or not self.neis_api_key.get_secret_value():
            raise RuntimeError("NEIS_API_KEY is required")
        return self.neis_api_key.get_secret_value()
