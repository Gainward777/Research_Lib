from controllers.utils.bootstrap.dependencies import ApplicationContainer
from models.commands import CreateItemCommand


async def run_ingestion(
    container: ApplicationContainer,
    command: CreateItemCommand,
    idempotency_key: str | None = None,
):
    return await container.ingestion.ingest(command, idempotency_key=idempotency_key)
