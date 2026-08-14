import argparse
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from controllers.utils.bootstrap.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up Research Library durable data")
    parser.add_argument("--output", type=Path, default=Path("backups"))
    args = parser.parse_args()
    settings = Settings()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = args.output / timestamp
    destination.mkdir(parents=True, exist_ok=False)
    if settings.library_brain_root.exists():
        shutil.copytree(settings.library_brain_root, destination / "brain")
    if settings.library_sqlite_path.exists():
        source = sqlite3.connect(settings.library_sqlite_path)
        target = sqlite3.connect(destination / "library.sqlite3")
        try:
            source.backup(target)
        finally:
            source.close()
            target.close()
    print(destination)


if __name__ == "__main__":
    main()
