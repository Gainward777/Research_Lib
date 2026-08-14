from models.enums import LibraryItemType


def classify_material(text: str) -> LibraryItemType:
    lowered = text.casefold()
    if "doi.org/" in lowered or "arxiv.org/" in lowered:
        return LibraryItemType.PUBLICATION
    if lowered.startswith("идея:") or lowered.startswith("idea:"):
        return LibraryItemType.IDEA
    return LibraryItemType.NOTE
