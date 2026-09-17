from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.access import SectionRef
from models.commands import SearchCommand
from views.mcp.search_view import render_search


async def library_search(
    container: ApplicationContainer,
    query: str,
    limit: int = 10,
    sections: list[str] | None = None,
) -> dict[str, object]:
    command = SearchCommand(
        query=query,
        limit=limit,
        sections=[SectionRef.parse(value) for value in sections or []],
    )
    return render_search(await container.search.search(command))
