import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from controllers.utils.BD.sqlite import Database
from models.access import (
    AccessPermission,
    AuthGrant,
    SectionRef,
    StoredToken,
    SubjectType,
)


class AccessStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_token(
        self,
        *,
        name: str,
        public_prefix: str,
        token_hash: str,
        subject_type: SubjectType,
        expires_at: datetime | None,
        created_by_token_id: str | None,
    ) -> StoredToken:
        token_id = f"tok_{uuid4().hex}"
        await self.database.execute(
            "INSERT INTO access_tokens("
            "id, name, public_prefix, token_hash, subject_type, expires_at, created_by_token_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                token_id,
                name,
                public_prefix,
                token_hash,
                subject_type.value,
                expires_at.isoformat() if expires_at else None,
                created_by_token_id,
            ),
        )
        result = await self.get_token(token_id)
        if result is None:
            raise RuntimeError("Token was not persisted")
        return result

    async def find_by_prefix(self, public_prefix: str) -> StoredToken | None:
        row = await self.database.fetchone(
            "SELECT * FROM access_tokens WHERE public_prefix = ?", (public_prefix,)
        )
        return self._token_from_row(row) if row is not None else None

    async def get_token(self, token_id: str) -> StoredToken | None:
        row = await self.database.fetchone(
            "SELECT * FROM access_tokens WHERE id = ?", (token_id,)
        )
        return self._token_from_row(row) if row is not None else None

    async def list_tokens(self) -> list[StoredToken]:
        rows = await self.database.fetchall(
            "SELECT * FROM access_tokens ORDER BY created_at, id"
        )
        return [self._token_from_row(row) for row in rows]

    async def touch(self, token_id: str) -> None:
        await self.database.execute(
            "UPDATE access_tokens SET last_used_at=CURRENT_TIMESTAMP WHERE id=?",
            (token_id,),
        )

    async def revoke(self, token_id: str) -> None:
        await self.database.execute(
            "UPDATE access_tokens SET revoked_at=CURRENT_TIMESTAMP WHERE id=?",
            (token_id,),
        )

    async def add_grant(
        self,
        token_id: str,
        section_id: str | None,
        permission: AccessPermission,
    ) -> None:
        await self.database.execute(
            "INSERT OR IGNORE INTO token_grants(token_id, section_id, permission) "
            "VALUES (?, ?, ?)",
            (token_id, section_id, permission.value),
        )

    async def remove_grant(
        self,
        token_id: str,
        section_id: str | None,
        permission: AccessPermission,
    ) -> None:
        if section_id is None:
            await self.database.execute(
                "DELETE FROM token_grants WHERE token_id=? AND section_id IS NULL "
                "AND permission=?",
                (token_id, permission.value),
            )
            return
        await self.database.execute(
            "DELETE FROM token_grants WHERE token_id=? AND section_id=? AND permission=?",
            (token_id, section_id, permission.value),
        )

    async def grants_for_token(self, token_id: str) -> list[AuthGrant]:
        rows = await self.database.fetchall(
            "SELECT g.permission, s.domain, s.key "
            "FROM token_grants g LEFT JOIN library_sections s ON s.id=g.section_id "
            "WHERE g.token_id=?",
            (token_id,),
        )
        return [
            AuthGrant(
                section=(
                    SectionRef(domain=str(row["domain"]), key=str(row["key"]))
                    if row["domain"] is not None
                    else None
                ),
                permission=str(row["permission"]),
            )
            for row in rows
        ]

    async def audit(
        self,
        *,
        actor_token_id: str | None,
        action: str,
        target_type: str,
        target_id: str | None = None,
        section_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self.database.execute(
            "INSERT INTO auth_audit_events("
            "id, actor_token_id, action, target_type, target_id, section_id, details_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"audit_{uuid4().hex}",
                actor_token_id,
                action,
                target_type,
                target_id,
                section_id,
                json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
            ),
        )

    @staticmethod
    def _token_from_row(row) -> StoredToken:
        return StoredToken(
            id=str(row["id"]),
            name=str(row["name"]),
            public_prefix=str(row["public_prefix"]),
            token_hash=str(row["token_hash"]),
            subject_type=str(row["subject_type"]),
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            last_used_at=row["last_used_at"],
            created_by_token_id=row["created_by_token_id"],
            created_at=str(row["created_at"]),
        )
