from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from controllers.api.app import create_app
from controllers.utils.bootstrap.settings import Settings
from tests.fakes import FakeGBrainAdapter


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        library_data_root=tmp_path / "library",
        library_api_token="test-api-token",
        mcp_auth_token="test-mcp-token",
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings, gbrain_factory=FakeGBrainAdapter)) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-api-token"}
