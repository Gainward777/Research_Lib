from pathlib import Path

import pytest

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from errors import NotFoundError
from models.access import (
    AccessPermission,
    SectionReadPolicy,
    SectionRef,
    SubjectType,
)
from models.commands import CreateItemCommand, SearchCommand
from models.enums import LibraryItemType, RelationType
from models.library_item import Relation
from tests.fakes import FakeGBrainAdapter


@pytest.mark.asyncio
async def test_project_sections_isolate_get_search_uploads_and_idempotency(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        library_data_root=tmp_path / "library",
        library_auth_enabled=True,
        library_token_pepper="integration-test-pepper",
    )
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

        developer = await container.token_service.create(
            root_context,
            name="backend-agent",
            subject_type=SubjectType.AGENT,
            grants=[(backend, AccessPermission.PUBLISH)],
        )
        backend_context = await container.authorization.authenticate(
            developer.token, legacy_surface="api"
        )

        backend_result = await container.items.create(
            CreateItemCommand(
                section=backend,
                type=LibraryItemType.DEVELOPMENT_CONTEXT,
                title="Shared marker backend",
                content="backend-only history",
            ),
            idempotency_key="same-external-key",
            auth=backend_context,
        )
        mobile_result = await container.items.create(
            CreateItemCommand(
                section=mobile,
                type=LibraryItemType.DEVELOPMENT_CONTEXT,
                title="Shared marker mobile",
                content="mobile-only history",
            ),
            idempotency_key="same-external-key",
            auth=root_context,
        )
        assert backend_result.item_id != mobile_result.item_id

        item, _slug = await container.items.get(
            backend_result.item_id, auth=backend_context
        )
        assert item.section == backend
        with pytest.raises(NotFoundError):
            await container.items.get(mobile_result.item_id, auth=backend_context)

        await container.items.add_relation(
            backend_result.item_id,
            Relation(type=RelationType.HAS_SOURCE, target_id=mobile_result.item_id),
            auth=root_context,
        )
        visible_backend, _slug = await container.items.get(
            backend_result.item_id, auth=backend_context
        )
        assert visible_backend.related == []

        hits = await container.search.search(
            SearchCommand(query="Shared marker"),
            auth=backend_context,
        )
        assert [hit.item_id for hit in hits] == [backend_result.item_id]

        mobile_section = await container.sections_store.require(mobile)
        upload = await container.attachments.save_upload(
            b"plain attachment",
            "report.txt",
            "text/plain",
            section_id=mobile_section.id,
        )
        with pytest.raises(ValueError, match="another section"):
            await container.items.create(
                CreateItemCommand(
                    section=backend,
                    type=LibraryItemType.DEVELOPMENT_CONTEXT,
                    title="Cannot steal upload",
                    attachment_upload_ids=[str(upload["upload_id"])],
                ),
                auth=backend_context,
            )
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_migration_creates_access_schema_and_required_section_columns(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        library_data_root=tmp_path / "library",
        library_token_pepper="migration-test-pepper",
    )
    container = await build_container(settings, gbrain_factory=FakeGBrainAdapter)
    try:
        tables = {
            str(row["name"])
            for row in await container.database.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "library_sections",
            "access_tokens",
            "token_grants",
            "auth_audit_events",
        }.issubset(tables)
        for table in ("library_items", "uploads", "ingest_jobs"):
            columns = {
                str(row["name"])
                for row in await container.database.fetchall(f"PRAGMA table_info({table})")
            }
            assert "section_id" in columns

        receipt_pk = [
            str(row["name"])
            for row in await container.database.fetchall(
                "PRAGMA table_info(idempotency_receipts)"
            )
            if int(row["pk"])
        ]
        assert receipt_pk == ["key", "section_id"]
    finally:
        await container.close()
