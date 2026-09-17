import argparse
import asyncio
import json
from dataclasses import dataclass

from controllers.utils.BD.access import AccessStore
from controllers.utils.BD.migrations import apply_migrations
from controllers.utils.BD.sections import SectionStore
from controllers.utils.BD.sqlite import Database
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.security.token_hasher import TokenHasher
from controllers.utils.services.access.authorization_service import AuthorizationService
from controllers.utils.services.access.section_service import SectionService
from controllers.utils.services.access.token_service import TokenService
from models.access import (
    AccessPermission,
    AuthorizationContext,
    SectionReadPolicy,
    SectionRef,
    SubjectType,
)


@dataclass
class AdminRuntime:
    database: Database
    authorization: AuthorizationService
    sections: SectionService
    tokens: TokenService


def _grant(value: str) -> list[tuple[SectionRef | None, AccessPermission]]:
    if value == AccessPermission.SYSTEM_ADMIN.value:
        return [(None, AccessPermission.SYSTEM_ADMIN)]
    section_text, separator, permissions = value.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError("grant must use section:permission,...")
    section = SectionRef.parse(section_text)
    return [(section, AccessPermission(item.strip())) for item in permissions.split(",")]


async def _runtime() -> AdminRuntime:
    settings = Settings()
    settings.ensure_directories()
    pepper = settings.library_token_pepper.get_secret_value()
    if not pepper:
        raise RuntimeError("LIBRARY_TOKEN_PEPPER is required for token administration")
    database = Database(settings.library_sqlite_path)
    await database.connect()
    await apply_migrations(database)
    access = AccessStore(database)
    sections_store = SectionStore(database)
    hasher = TokenHasher(pepper)
    authorization = AuthorizationService(settings, access, sections_store, hasher)
    return AdminRuntime(
        database=database,
        authorization=authorization,
        sections=SectionService(sections_store, access, authorization),
        tokens=TokenService(access, sections_store, hasher, authorization),
    )


async def _context(runtime: AdminRuntime, token: str | None) -> AuthorizationContext:
    if not token:
        return runtime.authorization.anonymous_context()
    context = await runtime.authorization.authenticate(token, legacy_surface="api")
    runtime.authorization.require_valid_token(context)
    return context


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="library-admin")
    parser.add_argument("--token", help="administrator bearer token")
    groups = parser.add_subparsers(dest="group", required=True)

    sections = groups.add_parser("sections").add_subparsers(dest="action", required=True)
    sections.add_parser("list")
    create = sections.add_parser("create")
    create.add_argument("section")
    create.add_argument("--title", required=True)
    create.add_argument(
        "--policy",
        choices=[item.value for item in SectionReadPolicy],
        default=SectionReadPolicy.RESTRICTED.value,
    )
    policy = sections.add_parser("set-policy")
    policy.add_argument("section")
    policy.add_argument("policy", choices=[item.value for item in SectionReadPolicy])

    tokens = groups.add_parser("tokens").add_subparsers(dest="action", required=True)
    bootstrap = tokens.add_parser("bootstrap")
    bootstrap.add_argument("--name", required=True)
    bootstrap.add_argument(
        "--subject-type",
        choices=[item.value for item in SubjectType],
        default=SubjectType.DEVELOPER.value,
    )
    create_token = tokens.add_parser("create")
    create_token.add_argument("--name", required=True)
    create_token.add_argument(
        "--subject-type",
        choices=[item.value for item in SubjectType],
        required=True,
    )
    create_token.add_argument("--grant", action="append", default=[])
    tokens.add_parser("list")
    revoke = tokens.add_parser("revoke")
    revoke.add_argument("token_id")

    grants = groups.add_parser("grants").add_subparsers(dest="action", required=True)
    for action in ("add", "remove"):
        command = grants.add_parser(action)
        command.add_argument("token_id")
        command.add_argument("section")
        command.add_argument("permission", choices=["read", "publish", "admin"])
    return parser


async def _run(args: argparse.Namespace) -> object:
    runtime = await _runtime()
    try:
        context = await _context(runtime, args.token)
        if args.group == "sections":
            if args.action == "list":
                return [
                    item.model_dump(mode="json")
                    for item in await runtime.sections.list(context)
                ]
            ref = SectionRef.parse(args.section)
            if args.action == "create":
                return (
                    await runtime.sections.create(
                        context,
                        ref,
                        title=args.title,
                        read_policy=SectionReadPolicy(args.policy),
                    )
                ).model_dump(mode="json")
            stored = await runtime.sections.sections.require(ref)
            return (
                await runtime.sections.update(
                    context,
                    stored.id,
                    read_policy=SectionReadPolicy(args.policy),
                )
            ).model_dump(mode="json")

        if args.group == "tokens":
            if args.action == "bootstrap":
                issued = await runtime.tokens.bootstrap_system_admin(
                    name=args.name,
                    subject_type=SubjectType(args.subject_type),
                )
                return issued.model_dump(mode="json")
            if args.action == "create":
                parsed_grants = [
                    grant
                    for value in args.grant
                    for grant in _grant(value)
                ]
                issued = await runtime.tokens.create(
                    context,
                    name=args.name,
                    subject_type=SubjectType(args.subject_type),
                    grants=parsed_grants,
                )
                return issued.model_dump(mode="json")
            if args.action == "list":
                return [
                    {
                        "id": item.id,
                        "name": item.name,
                        "public_prefix": item.public_prefix,
                        "subject_type": item.subject_type.value,
                        "expires_at": (
                            item.expires_at.isoformat() if item.expires_at else None
                        ),
                        "revoked_at": (
                            item.revoked_at.isoformat() if item.revoked_at else None
                        ),
                    }
                    for item in await runtime.tokens.list(context)
                ]
            await runtime.tokens.revoke(context, args.token_id)
            return {"revoked": args.token_id}

        section = SectionRef.parse(args.section)
        permission = AccessPermission(args.permission)
        operation = (
            runtime.tokens.add_grant
            if args.action == "add"
            else runtime.tokens.remove_grant
        )
        await operation(context, args.token_id, section, permission)
        return {
            "token_id": args.token_id,
            "section": section.value,
            "permission": permission.value,
            "action": args.action,
        }
    finally:
        await runtime.database.close()


def main() -> None:
    args = _parser().parse_args()
    result = asyncio.run(_run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
