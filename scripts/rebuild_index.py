import asyncio

from controllers.utils.bootstrap.dependencies import build_container
from controllers.workers.reindex_controller import rebuild_index


async def main() -> None:
    container = await build_container()
    try:
        count = await rebuild_index(container)
        print(f"Reindexed {count} pages")
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
