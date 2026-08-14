from pathlib import Path

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
