from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.commands import SearchCommand
from views.mcp.search_view import render_search


async def library_search(
    container: ApplicationContainer, query: str, limit: int = 10
) -> dict[str, object]:
    return render_search(await container.search.search(SearchCommand(query=query, limit=limit)))
