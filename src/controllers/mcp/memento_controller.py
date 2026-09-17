from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.memento import DevelopmentContextQuery, PublishDevelopmentContext
from views.mcp.memento_view import render_context_bundle, render_context_receipt


async def library_get_context(
    container: ApplicationContainer,
    *,
    query: str,
    project: str = "",
    repository: str = "",
    work_item: str | None = None,
    limit: int = 20,
) -> dict[str, object]:
    request = DevelopmentContextQuery(
        query=query,
        project=project,
        repository=repository,
        work_item=work_item,
        limit=limit,
    )
    return render_context_bundle(await container.memento.get_context(request))


async def library_publish_context(
    container: ApplicationContainer,
    payload: dict[str, object],
    idempotency_key: str,
) -> dict[str, object]:
    context = PublishDevelopmentContext.model_validate(payload)
    return render_context_receipt(
        await container.memento.publish(context, idempotency_key=idempotency_key)
    )
