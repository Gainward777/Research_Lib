import re
import unicodedata
from datetime import UTC
from pathlib import Path
from typing import Any

import yaml

from controllers.utils.BD.sections import SectionStore
from controllers.utils.BD.sqlite import Database
from controllers.utils.infrastructure.filesystem.atomic_writer import atomic_write_text
from models.access import SectionDomain, SectionRef
from models.enums import LibraryItemType
from models.library_item import LibraryItem

TYPE_DIRECTORIES: dict[LibraryItemType, str] = {
    LibraryItemType.EXPERIMENT: "experiments",
    LibraryItemType.EXPERIMENT_REPORT: "reports",
    LibraryItemType.IDEA: "ideas",
    LibraryItemType.PUBLICATION: "publications",
    LibraryItemType.METHOD: "methods",
    LibraryItemType.CONCEPT: "concepts",
    LibraryItemType.MODEL: "models",
    LibraryItemType.DATASET: "datasets",
    LibraryItemType.SOURCE: "sources",
    LibraryItemType.NOTE: "inbox",
    LibraryItemType.DEVELOPMENT_CONTEXT: "memento",
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return normalized[:80] or "item"


class MarkdownItemRepository:
    def __init__(
        self, brain_root: Path, database: Database, sections: SectionStore | None = None
    ) -> None:
        self.brain_root = brain_root
        self.database = database
        self.sections = sections or SectionStore(database)

    async def save(self, item: LibraryItem) -> str:
        section = await self.sections.ensure(item.section)
        if item.section.tag not in item.tags:
            item.tags.append(item.section.tag)
        existing = await self.database.fetchone(
            "SELECT path, slug, created_at FROM library_items WHERE id = ?", (item.id,)
        )
        if existing:
            relative_path = Path(existing["path"])
            slug = str(existing["slug"])
        else:
            folder = TYPE_DIRECTORIES[item.type]
            year = item.created_at.astimezone(UTC).strftime("%Y")
            base_slug = slugify(item.title)
            relative_path = Path(folder) / year / f"{base_slug}-{item.id[-8:]}.md"
            slug = relative_path.with_suffix("").as_posix()

        path = self.brain_root / relative_path
        atomic_write_text(path, self.render(item))
        await self.database.execute(
            "INSERT INTO library_items("
            "id, path, slug, type, title, section_id, created_at, updated_at, indexed"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0) "
            "ON CONFLICT(id) DO UPDATE SET path=excluded.path, slug=excluded.slug, "
            "type=excluded.type, title=excluded.title, section_id=excluded.section_id, "
            "updated_at=excluded.updated_at, indexed=0",
            (
                item.id,
                relative_path.as_posix(),
                slug,
                item.type.value,
                item.title,
                section.id,
                item.created_at.isoformat(),
                item.updated_at.isoformat(),
            ),
        )
        await self._backfill_dependents(item, section.id)
        return slug

    async def mark_indexed(self, item_id: str, indexed: bool = True) -> None:
        await self.database.execute(
            "UPDATE library_items SET indexed = ? WHERE id = ?", (int(indexed), item_id)
        )

    async def get(self, item_id_or_slug: str) -> tuple[LibraryItem, str] | None:
        row = await self.database.fetchone(
            "SELECT path, slug FROM library_items WHERE id = ? OR slug = ?",
            (item_id_or_slug, item_id_or_slug),
        )
        if row:
            path = self.brain_root / row["path"]
            if path.exists():
                return self.parse(path.read_text(encoding="utf-8")), str(row["slug"])

        for path in self.iter_pages():
            raw = path.read_text(encoding="utf-8")
            item = self.parse(raw)
            relative_path = path.relative_to(self.brain_root)
            slug = relative_path.with_suffix("").as_posix()
            if item.id == item_id_or_slug or slug == item_id_or_slug:
                await self._register(item, relative_path, slug)
                if "section:" not in raw.split("---", 2)[1]:
                    atomic_write_text(path, self.render(item))
                return item, slug
        return None

    def iter_pages(self) -> list[Path]:
        if not self.brain_root.exists():
            return []
        return sorted(
            path
            for path in self.brain_root.rglob("*.md")
            if "_system" not in path.relative_to(self.brain_root).parts
        )

    async def rebuild_catalog(self) -> int:
        count = 0
        for path in self.iter_pages():
            raw = path.read_text(encoding="utf-8")
            item = self.parse(raw)
            if item.section.tag not in item.tags:
                item.tags.append(item.section.tag)
            relative_path = path.relative_to(self.brain_root)
            await self._register(item, relative_path, relative_path.with_suffix("").as_posix())
            if "section:" not in raw.split("---", 2)[1]:
                atomic_write_text(path, self.render(item))
            count += 1
        return count

    async def _register(self, item: LibraryItem, relative_path: Path, slug: str) -> None:
        section = await self.sections.ensure(item.section)
        await self.database.execute(
            "INSERT INTO library_items("
            "id, path, slug, type, title, section_id, created_at, updated_at, indexed"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0) ON CONFLICT(id) DO UPDATE SET "
            "path=excluded.path, slug=excluded.slug, type=excluded.type, "
            "title=excluded.title, section_id=excluded.section_id, "
            "updated_at=excluded.updated_at",
            (
                item.id,
                relative_path.as_posix(),
                slug,
                item.type.value,
                item.title,
                section.id,
                item.created_at.isoformat(),
                item.updated_at.isoformat(),
            ),
        )
        await self._backfill_dependents(item, section.id)

    async def _backfill_dependents(
        self, item: LibraryItem, section_id: str
    ) -> None:
        for attachment in item.attachments:
            await self.database.execute(
                "UPDATE uploads SET section_id=? WHERE id=?",
                (section_id, attachment.id),
            )
        await self.database.execute(
            "UPDATE ingest_jobs SET section_id=? WHERE item_id=?",
            (section_id, item.id),
        )
        await self.database.execute(
            "UPDATE idempotency_receipts SET section_id=? "
            "WHERE json_extract(response_json, '$.item_id')=?",
            (section_id, item.id),
        )

    @staticmethod
    def render(item: LibraryItem) -> str:
        data = item.model_dump(mode="json", exclude={"content", "summary"})
        data["related"] = [relation.model_dump(mode="json") for relation in item.related]
        data["attachments"] = [
            attachment.model_dump(mode="json") for attachment in item.attachments
        ]
        frontmatter = yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()
        sections = [f"---\n{frontmatter}\n---", f"# {item.title}"]
        if item.summary:
            sections.extend(["## Резюме", item.summary])
        if item.content:
            sections.extend(["## Содержание", item.content])
        if item.attachments:
            rendered_attachments = []
            for attachment in item.attachments:
                label = attachment.original_name or Path(attachment.path).name
                if attachment.mime_type.startswith("image/"):
                    rendered_attachments.append(f"![[{attachment.path}|{label}]]")
                else:
                    rendered_attachments.append(f"[[{attachment.path}|{label}]]")
            sections.extend(["## Вложения", "\n".join(rendered_attachments)])
        return "\n\n".join(sections).rstrip() + "\n"

    @staticmethod
    def parse(content: str) -> LibraryItem:
        if not content.startswith("---\n"):
            raise ValueError("Markdown page has no YAML frontmatter")
        _, raw_frontmatter, body = content.split("---", 2)
        data: dict[str, Any] = yaml.safe_load(raw_frontmatter) or {}
        if "section" not in data:
            if data.get("type") == LibraryItemType.DEVELOPMENT_CONTEXT.value:
                project = str((data.get("metadata") or {}).get("project") or "_unassigned")
                try:
                    data["section"] = SectionRef(
                        domain=SectionDomain.MEMENTO, key=project
                    ).model_dump(mode="json")
                except ValueError:
                    data["section"] = SectionRef.parse(
                        "memento/_unassigned"
                    ).model_dump(mode="json")
            else:
                data["section"] = SectionRef.parse(
                    "research/main"
                ).model_dump(mode="json")
        summary = ""
        main_content = ""
        if "## Резюме" in body:
            summary_part = body.split("## Резюме", 1)[1]
            if "## Содержание" in summary_part:
                summary, main_content = summary_part.split("## Содержание", 1)
            else:
                summary = summary_part
        elif "## Содержание" in body:
            main_content = body.split("## Содержание", 1)[1]
        if "## Вложения" in summary:
            summary = summary.split("## Вложения", 1)[0]
        if "## Вложения" in main_content:
            main_content = main_content.split("## Вложения", 1)[0]
        data["content"] = main_content.strip()
        data["summary"] = summary.strip()
        return LibraryItem.model_validate(data)
