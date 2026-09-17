import pytest

from controllers.utils.bootstrap.settings import Settings


def test_router_uses_requested_default_model() -> None:
    settings = Settings()

    assert settings.library_router_model == "gpt-4.1-mini"
    assert settings.library_gbrain_think_model == "openai:gpt-4.1-mini"


def test_openai_key_is_required_only_when_telegram_is_enabled() -> None:
    Settings(telegram_bot_token="")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(telegram_bot_token="telegram-token", openai_api_key="")

    enabled = Settings(telegram_bot_token="telegram-token", openai_api_key="openai-key")
    assert enabled.openai_api_key.get_secret_value() == "openai-key"
