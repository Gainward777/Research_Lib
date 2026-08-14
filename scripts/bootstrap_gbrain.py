import asyncio

from controllers.utils.bootstrap.dependencies import build_container


async def main() -> None:
    container = await build_container()
    try:
        healthy = await container.gbrain.health()
        if not healthy:
            raise SystemExit("GBrain health check failed")
        print(f"GBrain mode '{container.settings.library_gbrain_mode}' is ready")
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
