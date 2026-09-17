import logging
from time import perf_counter
from typing import Any

from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from controllers.utils.infrastructure.observability.logging import log_event
from controllers.utils.infrastructure.observability.metrics import MetricsRecorder
from models.commands import SearchCommand
from models.library_item import LibraryItem
from models.results import AnswerResult, SearchHit

logger = logging.getLogger(__name__)


class ObservableGBrainAdapter(GBrainAdapter):
    def __init__(
        self,
        *args: Any,
        metrics: MetricsRecorder,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.metrics = metrics

    async def _observe(self, operation: str, call):
        started = perf_counter()
        outcome = "error"
        try:
            result = await call()
            outcome = "success"
            return result
        except Exception as exc:
            outcome = "timeout" if "timed out" in str(exc).casefold() else "error"
            raise
        finally:
            duration = perf_counter() - started
            self.metrics.record_gbrain(
                operation=operation,
                outcome=outcome,
                duration_seconds=duration,
            )
            log_event(
                logger,
                "gbrain.operation.completed",
                operation=operation,
                outcome=outcome,
                duration_ms=round(duration * 1000, 3),
                error_code=None if outcome == "success" else outcome,
            )

    async def health(self) -> bool:
        started = perf_counter()
        result = await super().health()
        outcome = "success" if result else "error"
        duration = perf_counter() - started
        self.metrics.record_gbrain(
            operation="health",
            outcome=outcome,
            duration_seconds=duration,
        )
        log_event(
            logger,
            "gbrain.operation.completed",
            operation="health",
            outcome=outcome,
            duration_ms=round(duration * 1000, 3),
            error_code=None if result else "unavailable",
        )
        return result

    async def index(self, item: LibraryItem) -> None:
        await self._observe("put", lambda: super(ObservableGBrainAdapter, self).index(item))

    async def search(self, command: SearchCommand) -> list[SearchHit]:
        return await self._observe(
            "search",
            lambda: super(ObservableGBrainAdapter, self).search(command),
        )

    async def query(self, command: SearchCommand) -> list[SearchHit]:
        return await self._observe(
            "search",
            lambda: super(ObservableGBrainAdapter, self).query(command),
        )

    async def think(self, command: SearchCommand) -> AnswerResult:
        return await self._observe(
            "think",
            lambda: super(ObservableGBrainAdapter, self).think(command),
        )
