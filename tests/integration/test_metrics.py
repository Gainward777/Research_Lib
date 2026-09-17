from pathlib import Path

from fastapi.testclient import TestClient

from controllers.api.app import create_app
from controllers.utils.bootstrap.settings import Settings
from tests.fakes import FakeGBrainAdapter


def test_metrics_endpoint_is_private_and_mcp_auth_is_measured(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        library_data_root=tmp_path / "library",
        library_api_token="api-secret",
        mcp_auth_token="mcp-secret",
        metrics_endpoint_enabled=True,
        metrics_auth_token="metrics-secret",
        otel_deployment_environment="test",
    )

    with TestClient(create_app(settings, gbrain_factory=FakeGBrainAdapter)) as client:
        health = client.get("/healthz", headers={"X-Request-ID": "req_external"})
        assert health.headers["X-Request-ID"] == "req_external"

        unauthorized = client.get("/metrics")
        assert unauthorized.status_code == 401
        assert unauthorized.headers["WWW-Authenticate"] == "Bearer"

        mcp_unauthorized = client.post("/mcp", json={})
        assert mcp_unauthorized.status_code == 401

        response = client.get(
            "/metrics",
            headers={"Authorization": "Bearer metrics-secret"},
        )
        openapi = client.get("/openapi.json").json()

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/plain")
    assert "mcp_auth_failures_total" in response.text
    assert 'reason="missing"' in response.text
    assert "library_pending_index_jobs" in response.text
    assert "metrics-secret" not in response.text
    assert "mcp-secret" not in response.text
    assert "api-secret" not in response.text
    assert "/metrics" not in openapi["paths"]
