from models.library_item import LibraryItem
from views.api.responses import ItemResponse


def render_item(item: LibraryItem, slug: str) -> ItemResponse:
    return ItemResponse(item=item, slug=slug)
