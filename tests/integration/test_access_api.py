import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from controllers.api.app import create_app
from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from models.access import (
    AccessPermission,
    SectionReadPolicy,
    SectionRef,
    SubjectType,
)
from models.commands import CreateItemCommand
from models.enums import LibraryItemType
from tests.fakes import FakeGBrainAdapter
from tests.integration.test_mcp import INITIALIZE_REQUEST


async def _seed(settings: Settings) -> dict[str, str]:
    container = await build_container(settings, gbrain_factory=FakeGBrainAdapter)
    try:
        assert container.token_service is not None
        root = await container.token_service.bootstrap_system_admin(name="root")
        root_context = await container.authorization.authenticate(
            root.token, legacy_surface="api"
        )
        backend = SectionRef.parse("memento/backend")
        mobile = SectionRef.parse("memento/mobile")
        for section in (backend, mobile):
            await container.section_service.create(
                root_context,
                section,
                title=section.value,
                read_policy=SectionReadPolicy.RESTRICTED,
            )
        publisher = await container.token_service.create(
            root_context,
            name="backend-publisher",
            subject_type=SubjectType.AGENT,
            grants=[(backend, AccessPermission.PUBLISH)],
        )
        reader = await container.token_service.create(
            root_context,
            name="backend-reader",
            subject_type=SubjectType.DEVELOPER,
            grants=[(backend, AccessPermission.READ)],
        )
        mobile_item = await container.items.create(
            CreateItemCommand(
                section=mobile,
                type=LibraryItemType.DEVELOPMENT_CONTEXT,
                title="Mobile private history",
            ),
            auth=root_context,
        )
        return {
            "root": root.token,
            "publisher": publisher.token,
            "reader": reader.token,
            "mobile_item": mobile_item.item_id,
        }
    finally:
        await container.close()


def test_dynamic_tokens_protect_rest_admin_and_mcp(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        library_data_root=tmp_path / "library",
        library_auth_enabled=True,
        library_token_pepper="api-test-pepper",
    )
    seeded = asyncio.run(_seed(settings))
    section = {"domain": "memento", "key": "backend"}
    publisher_headers = {"Authorization": f"Bearer {seeded['publisher']}"}

    with TestClient(create_app(settings, gbrain_factory=FakeGBrainAdapter)) as client:
        assert (
            client.get(
                f"/v1/items/{seeded['mobile_item']}",
                headers=publisher_headers,
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/v1/items/{seeded['mobile_item']}",
                headers={"Authorization": "Bearer invalid"},
            ).status_code
            == 401
        )

        created = client.post(
            "/v1/items",
            headers={**publisher_headers, "Idempotency-Key": "backend:item:1"},
            json={
                "section": section,
                "type": "development-context",
                "title": "Backend implementation",
            },
        )
        assert created.status_code == 200, created.text

        denied_section = client.post(
            "/v1/items",
            headers={**publisher_headers, "Idempotency-Key": "mobile:item:1"},
            json={
                "section": {"domain": "memento", "key": "mobile"},
                "type": "development-context",
                "title": "Mobile intrusion",
            },
        )
        assert denied_section.status_code == 403

        reader_denied = client.post(
            "/v1/items",
            headers={
                "Authorization": f"Bearer {seeded['reader']}",
                "Idempotency-Key": "backend:item:2",
            },
            json={
                "section": section,
                "type": "development-context",
                "title": "Reader cannot publish",
            },
        )
        assert reader_denied.status_code == 403

        tokens = client.get(
            "/v1/admin/tokens",
            headers={"Authorization": f"Bearer {seeded['root']}"},
        )
        assert tokens.status_code == 200
        assert all("token_hash" not in item and "token" not in item for item in tokens.json())

        issued = client.post(
            "/v1/admin/tokens",
            headers={"Authorization": f"Bearer {seeded['root']}"},
            json={
                "name": "ci",
                "subject_type": "ci",
                "grants": [{"section": section, "permission": "read"}],
            },
        )
        assert issued.status_code == 200
        assert issued.json()["token"].startswith("rl_")

        mcp_headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {seeded['publisher']}",
        }
        mcp_response = client.post(
            "/mcp", json=INITIALIZE_REQUEST, headers=mcp_headers
        )
        assert mcp_response.status_code == 200
