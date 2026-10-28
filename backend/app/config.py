from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HEZHANG_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/hezhang.db"
    jwt_secret: SecretStr
    access_token_minutes: int = Field(default=60, ge=1, le=1440)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("jwt_secret")
    @classmethod
    def require_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("HEZHANG_JWT_SECRET must contain at least 32 characters")
        return value
