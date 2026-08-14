from pathlib import Path

from controllers.utils.infrastructure.filesystem.atomic_writer import atomic_write_bytes


def install_research_schema(brain_root: Path) -> Path:
    source = Path(__file__).parents[2] / "schema-packs" / "research-v1"
    if not source.exists():
        raise RuntimeError(f"Bundled research-v1 schema pack is missing: {source}")
    target = brain_root / "_system" / "schemas" / "research-v1"
    for source_file in source.rglob("*"):
        if not source_file.is_file():
            continue
        target_file = target / source_file.relative_to(source)
        content = source_file.read_bytes()
        if not target_file.exists() or target_file.read_bytes() != content:
            atomic_write_bytes(target_file, content)
    return target
