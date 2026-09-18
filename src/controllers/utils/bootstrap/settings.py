from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GBRAIN_VERSION = "0.45.12.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    telegram_bot_token: str = ""
    library_telegram_access_token: SecretStr = SecretStr("")
    allowed_telegram_user_ids: list[int] = Field(default_factory=list)
    allowed_telegram_chat_ids: list[int] = Field(default_factory=list)

    openai_api_key: SecretStr = SecretStr("")
    library_router_model: str = "gpt-4.1-mini"
    library_router_timeout_seconds: float = Field(default=30, gt=0)
    library_router_context_turns: int = Field(default=12, ge=0, le=100)

    library_data_root: Path = Path("data/library")
    library_brain_root: Path | None = None
    library_attachments_root: Path | None = None
    library_sqlite_path: Path | None = None

    library_public_url: str = ""
    library_api_token: str = ""
    mcp_auth_token: str = ""
    library_auth_enabled: bool = False
    library_token_pepper: SecretStr = SecretStr("")
    library_public_sections_enabled: bool = False
    library_auth_fail_closed: bool = True
    library_legacy_api_grants: str = ""
    library_legacy_mcp_grants: str = ""
    library_default_research_section: str = "research/main"

    library_gbrain_command: str = "gbrain"
    library_gbrain_home: Path | None = None
    library_gbrain_version: str = DEFAULT_GBRAIN_VERSION
    library_gbrain_timeout_seconds: float = 120
    library_gbrain_no_embedding: bool = True
    library_gbrain_embedding_model: str = ""
    library_gbrain_embedding_dimensions: int | None = None
    library_gbrain_think_model: str = "openai:gpt-4.1-mini"

    library_image_max_long_side_px: int = 2048
    library_image_format: str = "webp"
    library_image_quality: int = 85
    library_keep_originals: bool = False
    library_image_vision_analysis: bool = False

    library_schema_mutation_mode: str = "propose"
    library_ingest_max_retries: int = 5
    library_media_group_settle_seconds: float = 3
    library_job_poll_seconds: float = 1
    log_level: str = "INFO"
    metrics_enabled: bool = False
    metrics_endpoint_enabled: bool = False
    metrics_auth_token: SecretStr = SecretStr("")
    metrics_allowed_projects: list[str] = Field(default_factory=list)
    otel_service_name: str = "research-library"
    otel_service_version: str = "0.1.0"
    otel_deployment_environment: str = "development"
    otel_metrics_exporter: str = "none"
    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: SecretStr = SecretStr("")
    otel_export_interval_milliseconds: int = Field(default=15000, ge=1000)
    otel_export_timeout_seconds: float = Field(default=10, gt=0)
    otel_max_export_batch_size: int = Field(default=512, ge=1, le=10000)

    @field_validator("allowed_telegram_user_ids", "allowed_telegram_chat_ids", mode="before")
    @classmethod
    def parse_int_list(cls, value: object) -> object:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value

    @field_validator("metrics_allowed_projects", mode="before")
    @classmethod
    def parse_string_list(cls, value: object) -> object:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [part.strip().casefold() for part in value.split(",") if part.strip()]
        return value

    @field_validator("library_gbrain_embedding_dimensions", mode="before")
    @classmethod
    def parse_optional_int(cls, value: object) -> object:
        return None if value in (None, "") else value

    @model_validator(mode="after")
    def validate_gbrain_embedding(self) -> "Settings":
        if not self.library_gbrain_version:
            raise ValueError("LIBRARY_GBRAIN_VERSION must pin the Docker runtime version")
        if not self.library_gbrain_no_embedding:
            if not self.library_gbrain_embedding_model:
                raise ValueError(
                    "LIBRARY_GBRAIN_EMBEDDING_MODEL is required when embeddings are enabled"
                )
            if self.library_gbrain_embedding_dimensions is None:
                raise ValueError(
                    "LIBRARY_GBRAIN_EMBEDDING_DIMENSIONS is required when embeddings are enabled"
                )
        if self.telegram_bot_token and not self.openai_api_key.get_secret_value():
            raise ValueError("OPENAI_API_KEY is required when TELEGRAM_BOT_TOKEN is configured")
        if (
            self.telegram_bot_token
            and self.library_auth_enabled
            and not self.library_telegram_access_token.get_secret_value()
        ):
            raise ValueError(
                "LIBRARY_TELEGRAM_ACCESS_TOKEN is required for Telegram when auth is enabled"
            )
        if not self.library_router_model:
            raise ValueError("LIBRARY_ROUTER_MODEL must not be empty")
        if self.otel_metrics_exporter not in {"none", "otlp"}:
            raise ValueError("OTEL_METRICS_EXPORTER must be none or otlp")
        if self.metrics_enabled:
            if self.otel_metrics_exporter != "otlp":
                raise ValueError("METRICS_ENABLED requires OTEL_METRICS_EXPORTER=otlp")
            if not self.otel_exporter_otlp_endpoint:
                raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT is required when metrics are enabled")
        if self.metrics_endpoint_enabled and not self.metrics_auth_token.get_secret_value():
            raise ValueError("METRICS_AUTH_TOKEN is required when metrics endpoint is enabled")
        metrics_token = self.metrics_auth_token.get_secret_value()
        reserved_tokens = {
            value
            for value in (
                self.library_api_token,
                self.mcp_auth_token,
                self.library_telegram_access_token.get_secret_value(),
            )
            if value
        }
        if metrics_token and metrics_token in reserved_tokens:
            raise ValueError(
                "METRICS_AUTH_TOKEN must differ from API, MCP, and Telegram tokens"
            )
        if self.library_auth_enabled and not self.library_token_pepper.get_secret_value():
            raise ValueError("LIBRARY_TOKEN_PEPPER is required when project auth is enabled")
        if self.library_auth_enabled and not self.library_auth_fail_closed:
            raise ValueError("LIBRARY_AUTH_FAIL_CLOSED must be true when project auth is enabled")
        return self

    def model_post_init(self, __context: object) -> None:
        if self.library_brain_root is None:
            self.library_brain_root = self.library_data_root / "brain"
        if self.library_attachments_root is None:
            self.library_attachments_root = self.library_brain_root / "attachments"
        if self.library_sqlite_path is None:
            self.library_sqlite_path = self.library_data_root / "library.sqlite3"
        if self.library_gbrain_home is None:
            self.library_gbrain_home = self.library_data_root / "gbrain"

    def ensure_directories(self) -> None:
        for path in (
            self.library_data_root,
            self.library_brain_root,
            self.library_attachments_root,
            self.library_sqlite_path.parent,
            self.library_gbrain_home,
        ):
            path.mkdir(parents=True, exist_ok=True)
