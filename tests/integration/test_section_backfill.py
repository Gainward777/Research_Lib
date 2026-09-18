from pathlib import Path

import pytest
import yaml

from controllers.utils.BD.markdown import MarkdownItemRepository
from controllers.utils.BD.migrations import apply_migrations
from controllers.utils.BD.sections import SectionStore
from controllers.utils.BD.sqlite import Database
from controllers.utils.bootstrap.settings import Settings

LEGACY_DEVELOPMENT_CONTEXT = """---
id: lib_legacy_backend
type: development-context
title: Legacy backend checkpoint
tags: []
metadata:
  project: Backend
---

# Legacy backend checkpoint

## Содержание

Historical implementation details.
"""

UNCLASSIFIED_NOTE = """---
id: lib_unclassified_note
type: note
title: Unclassified note
tags: []
---

# Unclassified note
"""


@pytest.mark.asyncio
async def test_section_backfill_dry_run_apply_verify_and_quarantine(
    tmp_path: Path,
) -> None:
    settings = Settings(_env_file=None, library_data_root=tmp_path / "library")
    settings.ensure_directories()
    database = Database(settings.library_sqlite_path)
    await database.connect()
    try:
        await apply_migrations(database)
        repository = MarkdownItemRepository(
            settings.library_brain_root, database, SectionStore(database)
        )
        legacy_path = settings.library_brain_root / "memento" / "legacy.md"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(LEGACY_DEVELOPMENT_CONTEXT, encoding="utf-8")

        dry_run = await repository.backfill_sections(apply=False)

        assert dry_run["ok"] is True
        assert dry_run["missing_section"] == 1
        assert dry_run["targets"] == {"memento/backend": 1}
        assert "section:" not in legacy_path.read_text(encoding="utf-8")

        applied = await repository.backfill_sections(apply=True)
        verification = await repository.verify_section_integrity()

        assert applied["applied"] is True
        assert verification["ok"] is True
        legacy_frontmatter = yaml.safe_load(
            legacy_path.read_text(encoding="utf-8").split("---", 2)[1]
        )
        assert legacy_frontmatter["section"] == {
            "domain": "memento",
            "key": "backend",
        }
        assert "section:memento/backend" in legacy_frontmatter["tags"]

        unclassified_path = settings.library_brain_root / "inbox" / "new.md"
        unclassified_path.parent.mkdir(parents=True, exist_ok=True)
        unclassified_path.write_text(UNCLASSIFIED_NOTE, encoding="utf-8")
        await repository.rebuild_catalog()

        quarantined_frontmatter = yaml.safe_load(
            unclassified_path.read_text(encoding="utf-8").split("---", 2)[1]
        )
        assert quarantined_frontmatter["section"] == {
            "domain": "research",
            "key": "_quarantine",
        }
        assert "section:research/_quarantine" in quarantined_frontmatter["tags"]
        post_quarantine = await repository.verify_section_integrity()
        assert post_quarantine["ok"] is True
        assert post_quarantine["quarantined_items"] == 1
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_startup_preflight_refuses_content_backfill_without_operator(
    tmp_path: Path,
) -> None:
    settings = Settings(_env_file=None, library_data_root=tmp_path / "library")
    settings.ensure_directories()
    database = Database(settings.library_sqlite_path)
    await database.connect()
    try:
        await apply_migrations(database)
        repository = MarkdownItemRepository(
            settings.library_brain_root, database, SectionStore(database)
        )
        legacy_path = settings.library_brain_root / "inbox" / "legacy.md"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(UNCLASSIFIED_NOTE, encoding="utf-8")

        with pytest.raises(RuntimeError, match="library-admin migration apply"):
            await repository.ensure_section_backfill_ready()

        assert "section:" not in legacy_path.read_text(encoding="utf-8")
    finally:
        await database.close()
