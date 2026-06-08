from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = Field(default="zhixue-workshop", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    sql_echo: bool = Field(default=False, alias="SQL_ECHO")

    database_url: str = Field(
        default="postgresql+asyncpg://zhixue:zhixue_password@localhost:5432/zhixue",
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
    llm_model_name: str = Field(
        default="mock-learning-model",
        validation_alias=AliasChoices("LLM_MODEL_NAME", "LLM_MODEL", "OPENAI_MODEL"),
    )
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"),
    )
    llm_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL", "OPENAI_API_BASE"),
    )
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_structured_max_retries: int = Field(default=2, alias="LLM_STRUCTURED_MAX_RETRIES")

    # ── 自适应难度配置 ──
    difficulty_default: str = Field(default="medium", alias="DIFFICULTY_DEFAULT")
    difficulty_threshold_low: float = Field(
        default=0.4,
        alias="DIFFICULTY_THRESHOLD_LOW",
        description="准确率低于此值时降低难度",
    )
    difficulty_threshold_high: float = Field(
        default=0.85,
        alias="DIFFICULTY_THRESHOLD_HIGH",
        description="准确率高于此值时提升难度",
    )
    difficulty_weak_point_trigger: int = Field(
        default=2,
        alias="DIFFICULTY_WEAK_POINT_TRIGGER",
        description="薄弱知识点数量达到此值时降低难度",
    )

    # ── 自进化触发配置 ──
    evolve_accuracy_threshold: float = Field(
        default=0.6,
        alias="EVOLVE_ACCURACY_THRESHOLD",
        description="诊断准确率低于此值时触发自进化",
    )
    evolve_weak_point_min: int = Field(
        default=2,
        alias="EVOLVE_WEAK_POINT_MIN",
        description="薄弱知识点数达到此值时触发自进化",
    )

    # ── 多模态运行时 ──
    multimodal_provider: str = Field(default="mock", alias="MULTIMODAL_PROVIDER")
    multimodal_storage_dir: str = Field(default="./storage/generated", alias="MULTIMODAL_STORAGE_DIR")
    multimodal_public_base_url: str = Field(default="", alias="MULTIMODAL_PUBLIC_BASE_URL")
    multimodal_job_poll_interval_seconds: int = Field(default=3, alias="MULTIMODAL_JOB_POLL_INTERVAL_SECONDS")
    multimodal_job_max_wait_seconds: int = Field(default=600, alias="MULTIMODAL_JOB_MAX_WAIT_SECONDS")

    agnes_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AGNES_API_KEY", "SAPIENS_API_KEY", "MULTIMODAL_API_KEY"),
    )
    agnes_base_url: str = Field(
        default="https://apihub.agnes-ai.com",
        validation_alias=AliasChoices("AGNES_BASE_URL", "SAPIENS_BASE_URL"),
    )
    agnes_auth_header: str = Field(default="Authorization", alias="AGNES_AUTH_HEADER")
    agnes_auth_scheme: str = Field(default="Bearer", alias="AGNES_AUTH_SCHEME")
    agnes_timeout_seconds: int = Field(default=180, alias="AGNES_TIMEOUT_SECONDS")
    agnes_chat_path: str = Field(default="/v1/chat/completions", alias="AGNES_CHAT_PATH")
    agnes_image_path: str = Field(default="/v1/images/generations", alias="AGNES_IMAGE_PATH")
    agnes_video_create_path: str = Field(default="/v1/videos", alias="AGNES_VIDEO_CREATE_PATH")
    agnes_video_status_path: str = Field(default="/v1/videos/{job_id}", alias="AGNES_VIDEO_STATUS_PATH")
    agnes_chat_model: str = Field(default="agnes-2.0-flash", alias="AGNES_CHAT_MODEL")
    agnes_image_model: str = Field(default="agnes-image-2.1-flash", alias="AGNES_IMAGE_MODEL")
    agnes_video_model: str = Field(default="agnes-video-v2.0", alias="AGNES_VIDEO_MODEL")
    agnes_image_url_json_path: str = Field(default="data.0.url", alias="AGNES_IMAGE_URL_JSON_PATH")
    agnes_image_b64_json_path: str = Field(default="data.0.b64_json", alias="AGNES_IMAGE_B64_JSON_PATH")
    agnes_video_job_id_json_path: str = Field(default="id", alias="AGNES_VIDEO_JOB_ID_JSON_PATH")
    agnes_video_url_json_path: str = Field(default="video_url", alias="AGNES_VIDEO_URL_JSON_PATH")
    agnes_video_status_json_path: str = Field(default="status", alias="AGNES_VIDEO_STATUS_JSON_PATH")

    agent_max_iterations: int = Field(default=15, alias="AGENT_MAX_ITERATIONS")
    agent_max_tool_calls: int = Field(default=30, alias="AGENT_MAX_TOOL_CALLS")
    agent_max_replans: int = Field(default=5, alias="AGENT_MAX_REPLANS")
    agent_worker_concurrency: int = Field(default=4, alias="AGENT_WORKER_CONCURRENCY")
    agent_inline_fallback: bool = Field(default=True, alias="AGENT_INLINE_FALLBACK")
    agent_inline_fallback_delay_seconds: float = Field(default=3.0, alias="AGENT_INLINE_FALLBACK_DELAY_SECONDS")

    embedding_provider: str = Field(default="mock", alias="EMBEDDING_PROVIDER")
    embedding_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("EMBEDDING_API_KEY", "OPENAI_EMBEDDING_API_KEY"),
    )
    embedding_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("EMBEDDING_BASE_URL", "OPENAI_EMBEDDING_BASE_URL"),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "OPENAI_EMBEDDING_MODEL"),
    )
    embedding_dimension: int = Field(default=1024, alias="EMBEDDING_DIMENSION")
    embedding_allow_mock_fallback: bool = Field(
        default=True,
        alias="EMBEDDING_ALLOW_MOCK_FALLBACK",
    )

    storage_provider: str = Field(default="local", alias="STORAGE_PROVIDER")
    local_storage_root: str = Field(default="./storage", alias="LOCAL_STORAGE_ROOT")
    upload_dir: str = Field(default="./storage/uploads", alias="UPLOAD_DIR")

    backend_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="BACKEND_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / "backend" / ".env", PROJECT_ROOT / ".env"),
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
