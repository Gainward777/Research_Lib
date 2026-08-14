from controllers.utils.bootstrap.dependencies import ApplicationContainer


async def rebuild_index(container: ApplicationContainer) -> int:
    count = 0
    for page in container.repository.iter_pages():
        item = container.repository.parse(page.read_text(encoding="utf-8"))
        await container.gbrain.index(item)
        await container.repository.mark_indexed(item.id)
        count += 1
    return count
