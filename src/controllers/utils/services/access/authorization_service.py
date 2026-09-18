import hmac
from datetime import UTC, datetime

from controllers.utils.BD.access import AccessStore
from controllers.utils.BD.sections import SectionStore
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.observability.metrics import (
    MetricsRecorder,
    NoOpMetricsRecorder,
)
from controllers.utils.infrastructure.security.token_hasher import TokenHasher
from errors import AuthenticationRequiredError, NotFoundError, PermissionDeniedError
from models.access import (
    AccessPermission,
    AuthGrant,
    AuthorizationContext,
    AuthPrincipal,
    LibrarySection,
    SectionDomain,
    SectionReadPolicy,
    SectionRef,
    SectionStatus,
)

_PERMISSION_RANK = {
    AccessPermission.READ: 1,
    AccessPermission.PUBLISH: 2,
    AccessPermission.ADMIN: 3,
}


def parse_legacy_grants(value: str) -> list[AuthGrant]:
    grants: list[AuthGrant] = []
    for entry in (part.strip() for part in value.split(";")):
        if not entry:
            continue
        if entry == AccessPermission.SYSTEM_ADMIN.value:
            grants.append(AuthGrant(section=None, permission=AccessPermission.SYSTEM_ADMIN))
            continue
        section_text, separator, permissions_text = entry.partition(":")
        if not separator:
            raise ValueError(f"Invalid legacy grant: {entry}")
        section = SectionRef.parse(section_text)
        for permission_text in permissions_text.split(","):
            permission = AccessPermission(permission_text.strip())
            if permission == AccessPermission.SYSTEM_ADMIN:
                raise ValueError("system_admin cannot be scoped to a section")
            grants.append(AuthGrant(section=section, permission=permission))
    return grants


class AuthorizationService:
    def __init__(
        self,
        settings: Settings,
        access_store: AccessStore,
        section_store: SectionStore,
        token_hasher: TokenHasher | None,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self.settings = settings
        self.access_store = access_store
        self.section_store = section_store
        self.token_hasher = token_hasher
        self.metrics = metrics or NoOpMetricsRecorder()

    @staticmethod
    def anonymous_context(*, invalid: bool = False) -> AuthorizationContext:
        return AuthorizationContext(
            principal=AuthPrincipal(id="anonymous", name="Anonymous"),
            anonymous=True,
            invalid_token=invalid,
        )

    @staticmethod
    def system_context() -> AuthorizationContext:
        return AuthorizationContext(
            principal=AuthPrincipal(id="system", name="Internal system"),
            authenticated=True,
            anonymous=False,
            grants=[AuthGrant(section=None, permission=AccessPermission.SYSTEM_ADMIN)],
        )

    async def authenticate(
        self, token: str | None, *, legacy_surface: str
    ) -> AuthorizationContext:
        if not token:
            return self.anonymous_context()
        dynamic = await self._authenticate_dynamic(token)
        if dynamic is not None:
            return dynamic
        legacy = self._authenticate_legacy(token, legacy_surface)
        if legacy is not None:
            return legacy
        return self.anonymous_context(invalid=True)

    async def _authenticate_dynamic(self, token: str) -> AuthorizationContext | None:
        if self.token_hasher is None:
            return None
        prefix = self.token_hasher.public_prefix(token)
        if prefix is None:
            return None
        stored = await self.access_store.find_by_prefix(prefix)
        if stored is None or not self.token_hasher.matches(token, stored.token_hash):
            return None
        now = datetime.now(UTC)
        if stored.revoked_at is not None:
            return self.anonymous_context(invalid=True)
        if stored.expires_at is not None:
            expiry = stored.expires_at
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if expiry <= now:
                return self.anonymous_context(invalid=True)
        await self.access_store.touch(stored.id)
        return AuthorizationContext(
            principal=AuthPrincipal(
                id=stored.id,
                name=stored.name,
                subject_type=stored.subject_type,
            ),
            authenticated=True,
            anonymous=False,
            grants=await self.access_store.grants_for_token(stored.id),
        )

    def _authenticate_legacy(
        self, token: str, legacy_surface: str
    ) -> AuthorizationContext | None:
        if legacy_surface == "api":
            expected = self.settings.library_api_token
            mapping = self.settings.library_legacy_api_grants
        elif legacy_surface == "mcp":
            expected = self.settings.mcp_auth_token
            mapping = self.settings.library_legacy_mcp_grants
        else:
            raise ValueError(f"Unknown legacy surface: {legacy_surface}")
        if not expected or not hmac.compare_digest(token, expected):
            return None
        grants = (
            parse_legacy_grants(mapping)
            if self.settings.library_auth_enabled
            else [AuthGrant(section=None, permission=AccessPermission.SYSTEM_ADMIN)]
        )
        return AuthorizationContext(
            principal=AuthPrincipal(id=f"legacy:{legacy_surface}", name="Legacy token"),
            authenticated=True,
            anonymous=False,
            legacy=True,
            grants=grants,
        )

    def require_valid_token(self, context: AuthorizationContext) -> None:
        if context.invalid_token:
            raise AuthenticationRequiredError("Invalid, expired or revoked bearer token")

    @staticmethod
    def _is_system_admin(context: AuthorizationContext) -> bool:
        return any(
            grant.permission == AccessPermission.SYSTEM_ADMIN and grant.section is None
            for grant in context.grants
        )

    def has_permission(
        self,
        context: AuthorizationContext,
        section: SectionRef,
        permission: AccessPermission,
    ) -> bool:
        if self._is_system_admin(context):
            return True
        required = _PERMISSION_RANK[permission]
        return any(
            grant.section == section
            and grant.permission in _PERMISSION_RANK
            and _PERMISSION_RANK[grant.permission] >= required
            for grant in context.grants
        )

    async def can_read(
        self, context: AuthorizationContext, section_ref: SectionRef
    ) -> bool:
        if not self.settings.library_auth_enabled:
            return True
        section = await self.section_store.get_by_ref(section_ref)
        if section is None or section.status != SectionStatus.ACTIVE:
            return False
        self.metrics.record_section_read(policy=section.read_policy.value)
        if self.has_permission(context, section_ref, AccessPermission.READ):
            return True
        if (
            section.read_policy == SectionReadPolicy.PUBLIC
            and self.settings.library_public_sections_enabled
        ):
            return True
        return (
            section.read_policy == SectionReadPolicy.AUTHENTICATED
            and context.authenticated
            and not context.invalid_token
        )

    async def require_read(
        self, context: AuthorizationContext, section: SectionRef
    ) -> None:
        self.require_valid_token(context)
        if not await self.can_read(context, section):
            self.metrics.record_auth_denial(
                operation="read", domain=section.domain.value
            )
            raise NotFoundError("Resource not found")

    async def require_publish(
        self, context: AuthorizationContext, section: SectionRef
    ) -> None:
        if not self.settings.library_auth_enabled:
            return
        self.require_valid_token(context)
        stored_section = await self.section_store.get_by_ref(section)
        if stored_section is None or stored_section.status != SectionStatus.ACTIVE:
            self.metrics.record_auth_denial(
                operation="publish", domain=section.domain.value
            )
            raise PermissionDeniedError(f"Section is not active: {section.value}")
        if not context.authenticated:
            self.metrics.record_auth_denial(
                operation="publish", domain=section.domain.value
            )
            raise AuthenticationRequiredError("Bearer token is required")
        if not self.has_permission(context, section, AccessPermission.PUBLISH):
            self.metrics.record_auth_denial(
                operation="publish", domain=section.domain.value
            )
            raise PermissionDeniedError(f"Publish access denied for {section.value}")

    async def require_admin(
        self, context: AuthorizationContext, section: SectionRef | None = None
    ) -> None:
        if not self.settings.library_auth_enabled:
            return
        self.require_valid_token(context)
        if not context.authenticated:
            raise AuthenticationRequiredError("Bearer token is required")
        if section is None:
            if not self._is_system_admin(context):
                self.metrics.record_auth_denial(operation="admin", domain="_global")
                raise PermissionDeniedError("System administrator access required")
            return
        if not self.has_permission(context, section, AccessPermission.ADMIN):
            self.metrics.record_auth_denial(
                operation="admin", domain=section.domain.value
            )
            raise PermissionDeniedError(f"Admin access denied for {section.value}")

    async def resolve_readable_sections(
        self,
        context: AuthorizationContext,
        requested: list[SectionRef] | None = None,
        *,
        domain: SectionDomain | None = None,
    ) -> list[LibrarySection]:
        self.require_valid_token(context)
        candidates = await self.section_store.list()
        if requested is not None:
            requested_values = {ref.value for ref in requested}
            candidates = [s for s in candidates if s.ref.value in requested_values]
        if domain is not None:
            candidates = [s for s in candidates if s.ref.domain == domain]
        return [s for s in candidates if await self.can_read(context, s.ref)]

    async def resolve_publish_section(
        self,
        context: AuthorizationContext,
        requested: SectionRef | None,
        *,
        domain: SectionDomain,
    ) -> SectionRef:
        if not self.settings.library_auth_enabled:
            selected = requested or SectionRef.parse(
                self.settings.library_default_research_section
                if domain == SectionDomain.RESEARCH
                else "memento/_unassigned"
            )
            if selected.domain != domain:
                raise PermissionDeniedError("Section belongs to another domain")
            await self.section_store.ensure(selected)
            return selected
        self.require_valid_token(context)
        if requested is not None:
            if requested.domain != domain:
                raise PermissionDeniedError("Section belongs to another domain")
            await self.section_store.require(requested)
            await self.require_publish(context, requested)
            return requested
        if self._is_system_admin(context) and domain == SectionDomain.RESEARCH:
            default = SectionRef.parse(self.settings.library_default_research_section)
            await self.section_store.ensure(default)
            await self.require_publish(context, default)
            return default
        if self._is_system_admin(context):
            available = {
                section.ref.value: section.ref
                for section in await self.section_store.list()
                if section.ref.domain == domain
            }
        else:
            available: dict[str, SectionRef] = {}
            for grant in context.grants:
                if (
                    grant.section is None
                    or grant.section.domain != domain
                    or grant.permission
                    not in {AccessPermission.PUBLISH, AccessPermission.ADMIN}
                ):
                    continue
                stored = await self.section_store.get_by_ref(grant.section)
                if stored is not None and stored.status == SectionStatus.ACTIVE:
                    available[grant.section.value] = grant.section
        if len(available) != 1:
            raise PermissionDeniedError("Section must be specified explicitly")
        selected = next(iter(available.values()))
        await self.require_publish(context, selected)
        return selected

    def can_delegate(
        self,
        context: AuthorizationContext,
        section: SectionRef | None,
        permission: AccessPermission,
    ) -> bool:
        if permission == AccessPermission.SYSTEM_ADMIN:
            return self._is_system_admin(context)
        if section is None:
            return False
        return self.has_permission(context, section, AccessPermission.ADMIN)
