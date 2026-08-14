from models.library_item import LibraryItem


def render_item(item: LibraryItem, slug: str) -> dict[str, object]:
    return {"item": item.model_dump(mode="json"), "slug": slug}
