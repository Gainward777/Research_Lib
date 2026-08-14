from pathlib import Path

import yaml


def load_schema_pack(path: Path) -> dict[str, object]:
    return yaml.safe_load((path / "schema.yaml").read_text(encoding="utf-8"))
