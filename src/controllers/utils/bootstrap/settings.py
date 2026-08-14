from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    telegram_bot_token: str = ""
    allowed_telegram_user_ids: list[int] = Field(default_factory=list)
    allowed_telegram_chat_ids: list[int] = Field(default_factory=list)

    library_data_root: Path = Path("data/library")
    library_brain_root: Path | None = None
    library_attachments_root: Path | None = None
    library_sqlite_path: Path | None = None

    library_public_url: str = ""
    library_api_token: str = ""
    library_codex_token: str = ""

    library_gbrain_mode: str = "local"
    library_gbrain_command: str = "gbrain"
    library_gbrain_home: Path | None = None
    library_gbrain_version: str = ""
    library_gbrain_timeout_seconds: float = 30

    librarian_llm_base_url: str = ""
    librarian_llm_api_key: str = ""
    librarian_llm_model: str = ""
    librarian_llm_timeout_seconds: float = 60

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

    @field_validator("allowed_telegram_user_ids", "allowed_telegram_chat_ids", mode="before")
    @classmethod
    def parse_int_list(cls, value: object) -> object:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        return value

    @field_validator("library_gbrain_mode")
    @classmethod
    def validate_gbrain_mode(cls, value: str) -> str:
        if value not in {"local", "subprocess"}:
            raise ValueError("LIBRARY_GBRAIN_MODE must be local or subprocess")
        return value

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
