from controllers.utils.bootstrap.dependencies import ApplicationContainer
from views.mcp.item_view import render_item


async def library_get(container: ApplicationContainer, item_id_or_slug: str) -> dict[str, object]:
    item, slug = await container.items.get(item_id_or_slug)
    return render_item(item, slug)
