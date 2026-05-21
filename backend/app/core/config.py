from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="zhixue-workshop", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")

    database_url: str = Field(
        default="postgresql+psycopg://zhixue:zhixue_password@localhost:5432/zhixue",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    jwt_secret: str = Field(default="change_me_in_local_env", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=1440,
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    llm_model_name: str = Field(default="mock-learning-model", alias="LLM_MODEL_NAME")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")

    storage_provider: str = Field(default="local", alias="STORAGE_PROVIDER")
    local_storage_root: str = Field(default="./storage", alias="LOCAL_STORAGE_ROOT")
    upload_dir: str = Field(default="./storage/uploads", alias="UPLOAD_DIR")

    backend_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="BACKEND_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
