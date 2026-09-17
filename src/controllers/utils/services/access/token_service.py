from datetime import UTC, datetime

from controllers.utils.BD.access import AccessStore
from controllers.utils.BD.sections import SectionStore
from controllers.utils.infrastructure.security.token_hasher import TokenHasher
from controllers.utils.services.access.authorization_service import AuthorizationService
from errors import NotFoundError, PermissionDeniedError
from models.access import (
    AccessPermission,
    AuthorizationContext,
    IssuedToken,
    SectionRef,
    StoredToken,
    SubjectType,
)


class TokenService:
    def __init__(
        self,
        access: AccessStore,
        sections: SectionStore,
        hasher: TokenHasher,
        authorization: AuthorizationService,
    ) -> None:
        self.access = access
        self.sections = sections
        self.hasher = hasher
        self.authorization = authorization

    async def bootstrap_system_admin(
        self, *, name: str, subject_type: SubjectType = SubjectType.DEVELOPER
    ) -> IssuedToken:
        if await self.access.list_tokens():
            raise PermissionDeniedError("Bootstrap is only allowed before the first token")
        return await self._issue(
            name=name,
            subject_type=subject_type,
            expires_at=None,
            created_by_token_id=None,
            grants=[(None, AccessPermission.SYSTEM_ADMIN)],
        )

    async def create(
        self,
        context: AuthorizationContext,
        *,
        name: str,
        subject_type: SubjectType,
        expires_at: datetime | None = None,
        grants: list[tuple[SectionRef | None, AccessPermission]] | None = None,
    ) -> IssuedToken:
        grants = grants or []
        for section, permission in grants:
            if not self.authorization.can_delegate(context, section, permission):
                raise PermissionDeniedError("Cannot delegate a wider permission")
        if not grants:
            await self.authorization.require_admin(context)
        return await self._issue(
            name=name,
            subject_type=subject_type,
            expires_at=expires_at,
            created_by_token_id=self._actor(context),
            grants=grants,
        )

    async def _issue(
        self,
        *,
        name: str,
        subject_type: SubjectType,
        expires_at: datetime | None,
        created_by_token_id: str | None,
        grants: list[tuple[SectionRef | None, AccessPermission]],
    ) -> IssuedToken:
        resolved_grants: list[tuple[str | None, AccessPermission]] = []
        for section_ref, permission in grants:
            section_id = None
            if section_ref is not None:
                section_id = (await self.sections.require(section_ref)).id
            resolved_grants.append((section_id, permission))
        prefix, raw_token = self.hasher.generate()
        stored = await self.access.create_token(
            name=name,
            public_prefix=prefix,
            token_hash=self.hasher.digest(raw_token),
            subject_type=subject_type,
            expires_at=expires_at,
            created_by_token_id=created_by_token_id,
        )
        for section_id, permission in resolved_grants:
            await self.access.add_grant(stored.id, section_id, permission)
        await self.access.audit(
            actor_token_id=created_by_token_id,
            action="token.create",
            target_type="token",
            target_id=stored.id,
            details={"subject_type": subject_type.value},
        )
        await self._update_token_counts()
        return IssuedToken(
            id=stored.id,
            name=stored.name,
            public_prefix=stored.public_prefix,
            token=raw_token,
            subject_type=stored.subject_type,
            expires_at=stored.expires_at,
        )

    async def list(
        self, context: AuthorizationContext
    ) -> list[StoredToken]:
        await self.authorization.require_admin(context)
        return await self.access.list_tokens()

    async def revoke(self, context: AuthorizationContext, token_id: str) -> None:
        await self.authorization.require_admin(context)
        if await self.access.get_token(token_id) is None:
            raise NotFoundError(f"Token not found: {token_id}")
        await self.access.revoke(token_id)
        await self.access.audit(
            actor_token_id=self._actor(context),
            action="token.revoke",
            target_type="token",
            target_id=token_id,
        )
        await self._update_token_counts()

    async def add_grant(
        self,
        context: AuthorizationContext,
        token_id: str,
        section_ref: SectionRef | None,
        permission: AccessPermission,
    ) -> None:
        if not self.authorization.can_delegate(context, section_ref, permission):
            raise PermissionDeniedError("Cannot delegate a wider permission")
        if await self.access.get_token(token_id) is None:
            raise NotFoundError(f"Token not found: {token_id}")
        section_id = None
        if section_ref is not None:
            section_id = (await self.sections.require(section_ref)).id
        await self.access.add_grant(token_id, section_id, permission)
        await self.access.audit(
            actor_token_id=self._actor(context),
            action="grant.add",
            target_type="token",
            target_id=token_id,
            section_id=section_id,
            details={"permission": permission.value},
        )

    async def remove_grant(
        self,
        context: AuthorizationContext,
        token_id: str,
        section_ref: SectionRef | None,
        permission: AccessPermission,
    ) -> None:
        if not self.authorization.can_delegate(context, section_ref, permission):
            raise PermissionDeniedError("Cannot manage this grant")
        section_id = None
        if section_ref is not None:
            section_id = (await self.sections.require(section_ref)).id
        await self.access.remove_grant(token_id, section_id, permission)
        await self.access.audit(
            actor_token_id=self._actor(context),
            action="grant.remove",
            target_type="token",
            target_id=token_id,
            section_id=section_id,
            details={"permission": permission.value},
        )

    async def refresh_metrics(self) -> None:
        await self._update_token_counts()

    async def _update_token_counts(self) -> None:
        now = datetime.now(UTC)
        active = revoked = expired = 0
        for token in await self.access.list_tokens():
            if token.revoked_at is not None:
                revoked += 1
                continue
            expires_at = token.expires_at
            if expires_at is not None:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if expires_at <= now:
                    expired += 1
                    continue
            active += 1
        self.authorization.metrics.set_token_counts(
            active=active, revoked=revoked, expired=expired
        )

    @staticmethod
    def _actor(context: AuthorizationContext) -> str | None:
        return context.principal_id if context.principal_id.startswith("tok_") else None
