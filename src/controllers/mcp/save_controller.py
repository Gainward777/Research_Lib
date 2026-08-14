from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.commands import CreateItemCommand


async def library_save_item(
    container: ApplicationContainer, payload: dict[str, object], idempotency_key: str
) -> dict[str, object]:
    result = await container.items.create(
        CreateItemCommand.model_validate(payload), idempotency_key=idempotency_key
    )
    return result.model_dump(mode="json")
