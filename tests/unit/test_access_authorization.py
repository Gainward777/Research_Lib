from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from controllers.utils.BD.access import AccessStore
from controllers.utils.BD.migrations import apply_migrations
from controllers.utils.BD.sections import SectionStore
from controllers.utils.BD.sqlite import Database
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.security.token_hasher import TokenHasher
from controllers.utils.services.access.authorization_service import (
    AuthorizationService,
    parse_legacy_grants,
)
from controllers.utils.services.access.section_service import SectionService
from controllers.utils.services.access.token_service import TokenService
from errors import NotFoundError, PermissionDeniedError
from models.access import (
    AccessPermission,
    SectionReadPolicy,
    SectionRef,
    SubjectType,
)


@pytest.fixture
async def access_runtime(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        library_data_root=tmp_path / "library",
        library_auth_enabled=True,
        library_token_pepper="unit-test-pepper",
        library_public_sections_enabled=False,
    )
    settings.ensure_directories()
    database = Database(settings.library_sqlite_path)
    await database.connect()
    await apply_migrations(database)
    access = AccessStore(database)
    sections = SectionStore(database)
    hasher = TokenHasher(settings.library_token_pepper.get_secret_value())
    authorization = AuthorizationService(settings, access, sections, hasher)
    section_service = SectionService(sections, access, authorization)
    tokens = TokenService(access, sections, hasher, authorization)
    try:
        yield settings, database, access, sections, authorization, section_service, tokens
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_token_is_shown_once_and_only_hmac_is_stored(access_runtime) -> None:
    _settings, database, _access, _sections, authorization, _section_service, tokens = (
        access_runtime
    )
    issued = await tokens.bootstrap_system_admin(name="root")
    row = await database.fetchone("SELECT token_hash FROM access_tokens WHERE id=?", (issued.id,))

    assert issued.token.startswith(f"rl_{issued.public_prefix}_")
    assert row is not None
    assert issued.token not in str(row["token_hash"])
    assert len(str(row["token_hash"])) == 64

    context = await authorization.authenticate(issued.token, legacy_surface="api")
    assert context.authenticated
    assert context.principal_id == issued.id
    assert context.grants[0].permission == AccessPermission.SYSTEM_ADMIN


@pytest.mark.asyncio
async def test_permission_inheritance_expiration_and_revoke(access_runtime) -> None:
    _settings, _database, _access, _sections, authorization, section_service, tokens = (
        access_runtime
    )
    root = await tokens.bootstrap_system_admin(name="root")
    root_context = await authorization.authenticate(root.token, legacy_surface="api")
    backend = SectionRef.parse("memento/backend")
    await section_service.create(
        root_context,
        backend,
        title="Backend",
        read_policy=SectionReadPolicy.RESTRICTED,
    )
    developer = await tokens.create(
        root_context,
        name="developer",
        subject_type=SubjectType.DEVELOPER,
        grants=[(backend, AccessPermission.PUBLISH)],
    )
    developer_context = await authorization.authenticate(
        developer.token, legacy_surface="api"
    )

    assert authorization.has_permission(
        developer_context, backend, AccessPermission.READ
    )
    assert authorization.has_permission(
        developer_context, backend, AccessPermission.PUBLISH
    )
    assert not authorization.has_permission(
        developer_context, backend, AccessPermission.ADMIN
    )
    await authorization.require_read(developer_context, backend)
    await authorization.require_publish(developer_context, backend)
    assert not await authorization.can_read(
        developer_context, SectionRef.parse("research/main")
    )
    with pytest.raises(PermissionDeniedError):
        await authorization.require_admin(developer_context, backend)

    expired = await tokens.create(
        root_context,
        name="expired",
        subject_type=SubjectType.AGENT,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        grants=[(backend, AccessPermission.READ)],
    )
    assert (
        await authorization.authenticate(expired.token, legacy_surface="api")
    ).invalid_token

    await tokens.revoke(root_context, developer.id)
    assert (
        await authorization.authenticate(developer.token, legacy_surface="api")
    ).invalid_token


@pytest.mark.asyncio
async def test_public_authenticated_and_restricted_policies(access_runtime) -> None:
    settings, _database, _access, _sections, authorization, section_service, tokens = (
        access_runtime
    )
    root = await tokens.bootstrap_system_admin(name="root")
    root_context = await authorization.authenticate(root.token, legacy_surface="api")
    public = SectionRef.parse("research/public")
    authenticated = SectionRef.parse("research/team")
    restricted = SectionRef.parse("research/private")
    await section_service.create(
        root_context,
        public,
        title="Public",
        read_policy=SectionReadPolicy.PUBLIC,
    )
    await section_service.create(
        root_context,
        authenticated,
        title="Team",
        read_policy=SectionReadPolicy.AUTHENTICATED,
    )
    await section_service.create(
        root_context,
        restricted,
        title="Private",
        read_policy=SectionReadPolicy.RESTRICTED,
    )
    anonymous = authorization.anonymous_context()

    assert not await authorization.can_read(anonymous, public)
    assert not await authorization.can_read(anonymous, authenticated)
    assert await authorization.can_read(root_context, authenticated)
    settings.library_public_sections_enabled = True
    assert await authorization.can_read(anonymous, public)
    assert not await authorization.can_read(anonymous, restricted)
    with pytest.raises(NotFoundError):
        await authorization.require_read(anonymous, restricted)


def test_legacy_grants_parser_is_explicit() -> None:
    grants = parse_legacy_grants(
        "memento/backend:read,publish;research/main:read"
    )
    assert [(grant.section.value, grant.permission.value) for grant in grants] == [
        ("memento/backend", "read"),
        ("memento/backend", "publish"),
        ("research/main", "read"),
    ]
    assert parse_legacy_grants("") == []


@pytest.mark.asyncio
async def test_legacy_token_loses_access_when_compatibility_secret_is_removed(
    access_runtime,
) -> None:
    settings, _database, _access, _sections, authorization, _section_service, _tokens = (
        access_runtime
    )
    settings.library_api_token = "legacy-secret"
    settings.library_legacy_api_grants = "research/main:read"

    legacy = await authorization.authenticate("legacy-secret", legacy_surface="api")
    assert legacy.authenticated
    assert legacy.legacy

    settings.library_api_token = ""
    removed = await authorization.authenticate("legacy-secret", legacy_surface="api")
    assert removed.invalid_token
    assert not removed.authenticated
