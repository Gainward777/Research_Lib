from controllers.utils.BD.access import AccessStore
from controllers.utils.BD.sections import SectionStore
from controllers.utils.services.access.authorization_service import AuthorizationService
from errors import NotFoundError
from models.access import (
    AuthorizationContext,
    LibrarySection,
    SectionReadPolicy,
    SectionRef,
    SectionStatus,
)


class SectionService:
    def __init__(
        self,
        sections: SectionStore,
        access: AccessStore,
        authorization: AuthorizationService,
    ) -> None:
        self.sections = sections
        self.access = access
        self.authorization = authorization

    async def create(
        self,
        context: AuthorizationContext,
        ref: SectionRef,
        *,
        title: str,
        read_policy: SectionReadPolicy,
    ) -> LibrarySection:
        await self.authorization.require_admin(context)
        section = await self.sections.ensure(ref, title=title, read_policy=read_policy)
        await self.access.audit(
            actor_token_id=self._actor(context),
            action="section.create",
            target_type="section",
            target_id=section.id,
            section_id=section.id,
            details={"read_policy": read_policy.value},
        )
        return section

    async def list(self, context: AuthorizationContext) -> list[LibrarySection]:
        await self.authorization.require_admin(context)
        return await self.sections.list(include_archived=True)

    async def update(
        self,
        context: AuthorizationContext,
        section_id: str,
        *,
        read_policy: SectionReadPolicy | None = None,
        status: SectionStatus | None = None,
        title: str | None = None,
    ) -> LibrarySection:
        current = await self.sections.get(section_id)
        if current is None:
            raise NotFoundError(f"Section not found: {section_id}")
        await self.authorization.require_admin(context, current.ref)
        updated = await self.sections.update(
            section_id, read_policy=read_policy, status=status, title=title
        )
        await self.access.audit(
            actor_token_id=self._actor(context),
            action="section.update",
            target_type="section",
            target_id=section_id,
            section_id=section_id,
            details={
                "read_policy": updated.read_policy.value,
                "status": updated.status.value,
            },
        )
        return updated

    @staticmethod
    def _actor(context: AuthorizationContext) -> str | None:
        return context.principal_id if context.principal_id.startswith("tok_") else None
