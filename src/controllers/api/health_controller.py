from fastapi import APIRouter, Depends

from controllers.api.dependencies import get_container
from controllers.utils.bootstrap.dependencies import ApplicationContainer
from views.api.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=HealthResponse)
async def readiness(
    container: ApplicationContainer = Depends(get_container),
) -> HealthResponse:
    sqlite_ok = (await container.database.fetchone("SELECT 1 AS ok")) is not None
    volume_ok = container.settings.library_data_root.exists()
    gbrain_ok = await container.gbrain.health()
    checks = {"sqlite": sqlite_ok, "volume": volume_ok, "gbrain": gbrain_ok}
    ready = all(checks.values())
    container.observability.recorder.set_readiness(ready=ready)
    return HealthResponse(status="ok" if ready else "not_ready", checks=checks)
