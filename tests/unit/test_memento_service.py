from pathlib import Path

import pytest
from pydantic import ValidationError

from controllers.utils.bootstrap.dependencies import build_container
from controllers.utils.bootstrap.settings import Settings
from models.enums import LibraryItemType, RelationType
from models.memento import (
    DevelopmentContextKind,
    DevelopmentContextQuery,
    PublishDevelopmentContext,
)
from tests.fakes import FakeGBrainAdapter


@pytest.mark.asyncio
async def test_publish_and_find_context_in_fixed_blocks(tmp_path: Path) -> None:
    container = await build_container(
        Settings(library_data_root=tmp_path / "library"),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        decision = PublishDevelopmentContext(
            context_kind=DevelopmentContextKind.DECISION,
            project="platform",
            repository="backend-api",
            work_item="AUTH-142",
            title="Refresh token encryption",
            content="Refresh tokens are encrypted before persistence.",
            branch="feature/oauth",
            commit="4f8a12c",
            paths=["src/auth/oauth.py"],
        )
        first = await container.memento.publish(
            decision,
            idempotency_key="memento:AUTH-142:decision:1",
        )
        duplicate = await container.memento.publish(
            decision,
            idempotency_key="memento:AUTH-142:decision:1",
        )

        bundle = await container.memento.get_context(
            DevelopmentContextQuery(
                query="refresh token persistence",
                project="platform",
                repository="backend-api",
            )
        )

        assert duplicate.item_id == first.item_id
        assert [entry.item_id for entry in bundle.decisions] == [first.item_id]
        assert bundle.decisions[0].commit == "4f8a12c"
        assert bundle.decisions[0].paths == ["src/auth/oauth.py"]
        assert bundle.related_implementations == []
        assert bundle.known_problems == []
        assert bundle.tests_and_evidence == []
        assert bundle.checkpoints == []

        stored, slug = await container.items.get(first.item_id)
        assert stored.type == LibraryItemType.DEVELOPMENT_CONTEXT
        assert stored.metadata["context_kind"] == "decision"
        assert slug.startswith("memento/")
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_supersedes_keeps_old_page_and_adds_relation(tmp_path: Path) -> None:
    container = await build_container(
        Settings(library_data_root=tmp_path / "library"),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        first = await container.memento.publish(
            PublishDevelopmentContext(
                context_kind="checkpoint",
                project="platform",
                repository="backend-api",
                work_item="FEATURE-120",
                title="OAuth checkpoint",
                content="Callback is implemented; revoke remains.",
            ),
            idempotency_key="memento:FEATURE-120:checkpoint:1",
        )
        second = await container.memento.publish(
            PublishDevelopmentContext(
                context_kind="checkpoint",
                project="platform",
                repository="backend-api",
                work_item="FEATURE-120",
                title="OAuth checkpoint after revoke",
                content="Callback and revoke are implemented; integration tests remain.",
                supersedes_item_id=first.item_id,
            ),
            idempotency_key="memento:FEATURE-120:checkpoint:2",
        )

        old_item, _old_slug = await container.items.get(first.item_id)
        new_item, _new_slug = await container.items.get(second.item_id)

        assert old_item.content == "Callback is implemented; revoke remains."
        assert new_item.metadata["supersedes_item_id"] == first.item_id
        assert new_item.related[0].type == RelationType.CONTINUES
        assert new_item.related[0].target_id == first.item_id
        assert len(container.repository.iter_pages()) == 2
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_new_bug_finds_history_from_another_work_item(tmp_path: Path) -> None:
    container = await build_container(
        Settings(library_data_root=tmp_path / "library"),
        gbrain_factory=FakeGBrainAdapter,
    )
    try:
        original = await container.memento.publish(
            PublishDevelopmentContext(
                context_kind="implementation_snapshot",
                project="platform",
                repository="backend-api",
                work_item="AUTH-142",
                title="Session refresh implementation",
                content=(
                    "The session is renewed with a refresh token. Expired tokens "
                    "force the user to sign in again."
                ),
            ),
            idempotency_key="memento:AUTH-142:snapshot:1",
        )

        bundle = await container.memento.get_context(
            DevelopmentContextQuery(
                query="user is forced to sign in after token expiration",
                project="platform",
                repository="backend-api",
                work_item="BUG-731",
            )
        )

        assert bundle.work_item == "BUG-731"
        assert [entry.item_id for entry in bundle.related_implementations] == [original.item_id]
        assert bundle.related_implementations[0].work_item == "AUTH-142"
    finally:
        await container.close()


def test_publish_context_requires_work_identifier() -> None:
    with pytest.raises(ValidationError, match="work_item or work_context_id"):
        PublishDevelopmentContext(
            context_kind="decision",
            project="platform",
            title="Missing work scope",
            content="This record cannot be resumed safely.",
        )
