from uuid import uuid4

from controllers.utils.BD.sqlite import Database
from errors import NotFoundError
from models.access import (
    LibrarySection,
    SectionReadPolicy,
    SectionRef,
    SectionStatus,
)


class SectionStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def ensure(
        self,
        ref: SectionRef,
        *,
        title: str | None = None,
        read_policy: SectionReadPolicy | None = None,
    ) -> LibrarySection:
        existing = await self.get_by_ref(ref)
        if existing is not None:
            return existing
        section_id = f"sec_{uuid4().hex}"
        policy = read_policy or SectionReadPolicy.RESTRICTED
        await self.database.execute(
            "INSERT INTO library_sections(id, domain, key, title, read_policy) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                section_id,
                ref.domain.value,
                ref.key,
                title or ref.value,
                policy.value,
            ),
        )
        result = await self.get(section_id)
        if result is None:
            raise RuntimeError("Section was not persisted")
        return result

    async def get(self, section_id: str) -> LibrarySection | None:
        row = await self.database.fetchone(
            "SELECT * FROM library_sections WHERE id = ?", (section_id,)
        )
        return self._from_row(row) if row is not None else None

    async def get_by_ref(self, ref: SectionRef) -> LibrarySection | None:
        row = await self.database.fetchone(
            "SELECT * FROM library_sections WHERE domain = ? AND key = ?",
            (ref.domain.value, ref.key),
        )
        return self._from_row(row) if row is not None else None

    async def require(self, ref: SectionRef) -> LibrarySection:
        section = await self.get_by_ref(ref)
        if section is None:
            raise NotFoundError(f"Section not found: {ref.value}")
        return section

    async def list(self, *, include_archived: bool = False) -> list[LibrarySection]:
        sql = "SELECT * FROM library_sections"
        if not include_archived:
            sql += " WHERE status = 'active'"
        sql += " ORDER BY domain, key"
        return [self._from_row(row) for row in await self.database.fetchall(sql)]

    async def update(
        self,
        section_id: str,
        *,
        read_policy: SectionReadPolicy | None = None,
        status: SectionStatus | None = None,
        title: str | None = None,
    ) -> LibrarySection:
        current = await self.get(section_id)
        if current is None:
            raise NotFoundError(f"Section not found: {section_id}")
        await self.database.execute(
            "UPDATE library_sections SET title=?, read_policy=?, status=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                title or current.title,
                (read_policy or current.read_policy).value,
                (status or current.status).value,
                section_id,
            ),
        )
        updated = await self.get(section_id)
        if updated is None:
            raise RuntimeError("Section disappeared after update")
        return updated

    @staticmethod
    def _from_row(row) -> LibrarySection:
        return LibrarySection(
            id=str(row["id"]),
            ref=SectionRef(domain=str(row["domain"]), key=str(row["key"])),
            title=str(row["title"]),
            read_policy=str(row["read_policy"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
