from pathlib import Path

from controllers.utils.BD.sqlite import Database


async def apply_migrations(database: Database) -> None:
    await database.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    versions_dir = Path(__file__).parent / "versions"
    for migration in sorted(versions_dir.glob("*.sql")):
        applied = await database.fetchone(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (migration.name,)
        )
        if applied:
            continue
        sql = migration.read_text(encoding="utf-8")
        await database.executescript(
            f"BEGIN IMMEDIATE;\n{sql}\n"
            f"INSERT INTO schema_migrations(version) VALUES ('{migration.name}');\nCOMMIT;"
        )
