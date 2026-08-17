from pathlib import Path

import pytest

from controllers.utils.bootstrap.settings import Settings


def test_settings_derives_storage_paths(tmp_path: Path) -> None:
    settings = Settings(library_data_root=tmp_path / "data")

    assert settings.library_brain_root == tmp_path / "data" / "brain"
    assert settings.library_attachments_root == tmp_path / "data" / "brain" / "attachments"
    assert settings.library_sqlite_path == tmp_path / "data" / "library.sqlite3"


def test_settings_parses_telegram_allowlists() -> None:
    settings = Settings(
        allowed_telegram_user_ids="1, 2",
        allowed_telegram_chat_ids="10,20",
    )

    assert settings.allowed_telegram_user_ids == [1, 2]
    assert settings.allowed_telegram_chat_ids == [10, 20]


def test_gbrain_is_required_and_version_pinned() -> None:
    settings = Settings()

    assert settings.library_gbrain_version == "0.45.12.0"
    assert settings.library_gbrain_no_embedding is True


def test_gbrain_embedding_configuration_is_complete() -> None:
    with pytest.raises(ValueError, match="EMBEDDING_MODEL"):
        Settings(library_gbrain_no_embedding=False)


def test_empty_gbrain_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="must pin"):
        Settings(library_gbrain_version="")
