import json
import re
import unicodedata
from datetime import UTC
from pathlib import Path
from typing import Any, Literal

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

QUARANTINE_SECTION = SectionRef.parse("research/_quarantine")
MissingSectionMode = Literal["legacy", "quarantine"]


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
            frontmatter = self._frontmatter(raw)
            missing_section = "section" not in frontmatter
            original_tags = {str(tag) for tag in frontmatter.get("tags") or []}
            item = self.parse(raw)
            relative_path = path.relative_to(self.brain_root)
            slug = relative_path.with_suffix("").as_posix()
            if item.id == item_id_or_slug or slug == item_id_or_slug:
                await self._register(item, relative_path, slug)
                if missing_section or item.section.tag not in original_tags:
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
            frontmatter = self._frontmatter(raw)
            missing_section = "section" not in frontmatter
            original_tags = {str(tag) for tag in frontmatter.get("tags") or []}
            item = self.parse(raw)
            if item.section.tag not in item.tags:
                item.tags.append(item.section.tag)
            relative_path = path.relative_to(self.brain_root)
            await self._register(item, relative_path, relative_path.with_suffix("").as_posix())
            if missing_section or item.section.tag not in original_tags:
                atomic_write_text(path, self.render(item))
            count += 1
        return count

    async def backfill_sections(self, *, apply: bool) -> dict[str, Any]:
        state = await self.database.fetchone(
            "SELECT status FROM section_backfill_state WHERE id=1"
        )
        state_status = str(state["status"]) if state is not None else "pending"
        mode: MissingSectionMode = (
            "legacy" if state_status != "completed" else "quarantine"
        )
        candidates: list[dict[str, str]] = []
        errors: list[dict[str, str]] = []
        scanned = 0
        for path in self.iter_pages():
            scanned += 1
            relative_path = path.relative_to(self.brain_root).as_posix()
            try:
                data = self._frontmatter(path.read_text(encoding="utf-8"))
                if "section" in data:
                    continue
                target = (
                    self._legacy_section(data)
                    if mode == "legacy"
                    else QUARANTINE_SECTION
                )
                candidates.append(
                    {
                        "path": relative_path,
                        "type": str(data.get("type") or "unknown"),
                        "target_section": target.value,
                    }
                )
            except Exception as exc:
                errors.append({"path": relative_path, "error": type(exc).__name__})

        targets: dict[str, int] = {}
        for candidate in candidates:
            target = candidate["target_section"]
            targets[target] = targets.get(target, 0) + 1
        report: dict[str, Any] = {
            "ok": not errors,
            "status": state_status,
            "mode": mode,
            "scanned": scanned,
            "missing_section": len(candidates),
            "targets": targets,
            "candidates": candidates,
            "errors": errors,
            "applied": False,
        }
        if not apply:
            return report
        if errors:
            raise ValueError("Section backfill dry-run found unreadable Markdown files")
        if state_status == "completed":
            report["already_completed"] = True
            return report

        encoded_running = json.dumps(report, ensure_ascii=False, sort_keys=True)
        await self.database.execute(
            "UPDATE section_backfill_state SET status='running', report_json=?, "
            "started_at=COALESCE(started_at, CURRENT_TIMESTAMP), updated_at=CURRENT_TIMESTAMP "
            "WHERE id=1",
            (encoded_running,),
        )
        try:
            for candidate in candidates:
                path = self.brain_root / candidate["path"]
                item = self.parse(
                    path.read_text(encoding="utf-8"), missing_section="legacy"
                )
                if item.section.tag not in item.tags:
                    item.tags.append(item.section.tag)
                relative_path = path.relative_to(self.brain_root)
                await self._register(
                    item, relative_path, relative_path.with_suffix("").as_posix()
                )
                atomic_write_text(path, self.render(item))
            report["status"] = "completed"
            report["applied"] = True
            encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
            await self.database.execute(
                "UPDATE section_backfill_state SET status='completed', report_json=?, "
                "completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=1",
                (encoded,),
            )
            return report
        except Exception:
            report["status"] = "failed"
            encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
            await self.database.execute(
                "UPDATE section_backfill_state SET status='failed', report_json=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=1",
                (encoded,),
            )
            raise

    async def ensure_section_backfill_ready(self) -> None:
        report = await self.backfill_sections(apply=False)
        if report["errors"]:
            raise RuntimeError(
                "Section backfill preflight failed; run library-admin migration dry-run"
            )
        if report["status"] == "completed":
            return
        if report["missing_section"]:
            raise RuntimeError(
                "Section backfill is required; create a backup, then run "
                "library-admin migration apply before starting the service"
            )
        report["status"] = "completed"
        report["applied"] = True
        report["empty_backfill"] = True
        encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
        await self.database.execute(
            "UPDATE section_backfill_state SET status='completed', report_json=?, "
            "started_at=COALESCE(started_at, CURRENT_TIMESTAMP), "
            "completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=1",
            (encoded,),
        )

    async def verify_section_integrity(self) -> dict[str, Any]:
        failures: list[str] = []
        warnings: list[str] = []
        state = await self.database.fetchone(
            "SELECT status FROM section_backfill_state WHERE id=1"
        )
        state_status = str(state["status"]) if state is not None else "missing"
        if state_status != "completed":
            failures.append(f"section backfill state is {state_status}")

        markdown_missing_section = 0
        markdown_missing_tag = 0
        markdown_errors = 0
        for path in self.iter_pages():
            try:
                raw = path.read_text(encoding="utf-8")
                data = self._frontmatter(raw)
                if "section" not in data:
                    markdown_missing_section += 1
                    continue
                item = self.parse(raw)
                if item.section.tag not in {str(tag) for tag in data.get("tags") or []}:
                    markdown_missing_tag += 1
            except Exception:
                markdown_errors += 1
        if markdown_missing_section:
            failures.append(f"{markdown_missing_section} Markdown files have no section")
        if markdown_missing_tag:
            failures.append(f"{markdown_missing_tag} Markdown files have no section tag")
        if markdown_errors:
            failures.append(f"{markdown_errors} Markdown files cannot be parsed")

        null_counts: dict[str, int] = {}
        for table in ("library_items", "uploads", "ingest_jobs", "idempotency_receipts"):
            row = await self.database.fetchone(
                f"SELECT COUNT(*) AS count FROM {table} WHERE section_id IS NULL"
            )
            count = int(row["count"]) if row is not None else 0
            null_counts[table] = count
            if count:
                failures.append(f"{table} contains {count} rows without section")

        development_outside_memento = await self.database.fetchone(
            "SELECT COUNT(*) AS count FROM library_items i "
            "JOIN library_sections s ON s.id=i.section_id "
            "WHERE i.type='development-context' AND s.domain<>'memento'"
        )
        wrong_development_count = (
            int(development_outside_memento["count"])
            if development_outside_memento is not None
            else 0
        )
        if wrong_development_count:
            failures.append(
                f"{wrong_development_count} development-context items are outside Memento"
            )

        job_mismatches = await self.database.fetchone(
            "SELECT COUNT(*) AS count FROM ingest_jobs j "
            "JOIN library_items i ON i.id=j.item_id "
            "WHERE j.section_id<>i.section_id"
        )
        receipt_mismatches = await self.database.fetchone(
            "SELECT COUNT(*) AS count FROM idempotency_receipts r "
            "JOIN library_items i ON i.id=json_extract(r.response_json, '$.item_id') "
            "WHERE r.section_id<>i.section_id"
        )
        dependent_mismatches = {
            "ingest_jobs": int(job_mismatches["count"]) if job_mismatches else 0,
            "idempotency_receipts": (
                int(receipt_mismatches["count"]) if receipt_mismatches else 0
            ),
            "uploads": 0,
        }
        for path in self.iter_pages():
            try:
                item = self.parse(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            section = await self.sections.get_by_ref(item.section)
            if section is None:
                dependent_mismatches["uploads"] += len(item.attachments)
                continue
            for attachment in item.attachments:
                upload = await self.database.fetchone(
                    "SELECT section_id FROM uploads WHERE id=?", (attachment.id,)
                )
                if upload is None or str(upload["section_id"]) != section.id:
                    dependent_mismatches["uploads"] += 1
        for name, count in dependent_mismatches.items():
            if count:
                failures.append(f"{name} contains {count} cross-section references")

        quarantined = await self.database.fetchone(
            "SELECT COUNT(*) AS count FROM library_items i "
            "JOIN library_sections s ON s.id=i.section_id "
            "WHERE s.domain='research' AND s.key='_quarantine'"
        )
        quarantined_count = int(quarantined["count"]) if quarantined is not None else 0
        if quarantined_count:
            warnings.append(f"{quarantined_count} items require quarantine review")

        return {
            "ok": not failures,
            "backfill_status": state_status,
            "markdown_missing_section": markdown_missing_section,
            "markdown_missing_tag": markdown_missing_tag,
            "markdown_errors": markdown_errors,
            "null_section_rows": null_counts,
            "development_context_outside_memento": wrong_development_count,
            "dependent_section_mismatches": dependent_mismatches,
            "quarantined_items": quarantined_count,
            "failures": failures,
            "warnings": warnings,
        }

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
    def _frontmatter(content: str) -> dict[str, Any]:
        if not content.startswith("---\n"):
            raise ValueError("Markdown page has no YAML frontmatter")
        _, raw_frontmatter, _body = content.split("---", 2)
        data: dict[str, Any] = yaml.safe_load(raw_frontmatter) or {}
        if not isinstance(data, dict):
            raise ValueError("Markdown YAML frontmatter must be an object")
        return data

    @staticmethod
    def _legacy_section(data: dict[str, Any]) -> SectionRef:
        if data.get("type") == LibraryItemType.DEVELOPMENT_CONTEXT.value:
            project = str((data.get("metadata") or {}).get("project") or "_unassigned")
            try:
                return SectionRef(domain=SectionDomain.MEMENTO, key=project)
            except ValueError:
                return SectionRef.parse("memento/_unassigned")
        return SectionRef.parse("research/main")

    @classmethod
    def parse(
        cls,
        content: str,
        *,
        missing_section: MissingSectionMode = "quarantine",
    ) -> LibraryItem:
        if not content.startswith("---\n"):
            raise ValueError("Markdown page has no YAML frontmatter")
        _, raw_frontmatter, body = content.split("---", 2)
        data: dict[str, Any] = yaml.safe_load(raw_frontmatter) or {}
        if not isinstance(data, dict):
            raise ValueError("Markdown YAML frontmatter must be an object")
        if "section" not in data:
            section = (
                cls._legacy_section(data)
                if missing_section == "legacy"
                else QUARANTINE_SECTION
            )
            data["section"] = section.model_dump(mode="json")
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
