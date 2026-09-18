import logging
from time import perf_counter

from controllers.utils.infrastructure.observability.context import set_request_scope
from controllers.utils.infrastructure.observability.logging import log_event
from controllers.utils.infrastructure.observability.metrics import MetricsRecorder
from controllers.utils.services.access.context import current_authorization
from controllers.utils.services.librarian.search_service import SearchService
from controllers.utils.services.library.item_service import ItemService
from controllers.utils.services.library.memento_service import (
    BLOCK_BY_KIND,
    MementoService,
)
from errors import IdempotencyConflictError, SearchBackendError
from models.access import AuthorizationContext, SectionDomain
from models.memento import (
    DevelopmentContextBundle,
    DevelopmentContextQuery,
    PublishDevelopmentContext,
)
from models.results import SaveResult

logger = logging.getLogger(__name__)


class ObservableMementoService(MementoService):
    def __init__(
        self,
        items: ItemService,
        search: SearchService,
        metrics: MetricsRecorder,
    ) -> None:
        super().__init__(items, search)
        self.metrics = metrics

    async def publish(
        self,
        context: PublishDevelopmentContext,
        *,
        idempotency_key: str,
        auth: AuthorizationContext | None = None,
    ) -> SaveResult:
        authorization = auth or current_authorization()
        if not context.project:
            section = await self.items.authorization.resolve_publish_section(
                authorization,
                None,
                domain=SectionDomain.MEMENTO,
            )
            context = context.model_copy(update={"project": section.key})
        set_request_scope(
            project=context.project,
            repository=context.repository,
            work_item=context.work_item or context.work_context_id or "",
        )
        started = perf_counter()
        outcome = "internal_error"
        result: SaveResult | None = None
        try:
            result = await super().publish(
                context, idempotency_key=idempotency_key, auth=authorization
            )
            outcome = (
                "deduplicated"
                if result._deduplicated
                else "created"
                if result.indexed
                else "pending_index"
            )
            return result
        except IdempotencyConflictError:
            outcome = "idempotency_conflict"
            raise
        except SearchBackendError:
            outcome = "gbrain_error"
            raise
        except ValueError:
            outcome = "validation_error"
            raise
        finally:
            duration = perf_counter() - started
            self.metrics.record_memento_publish(
                kind=context.context_kind.value,
                outcome=outcome,
                project=context.project,
                duration_seconds=duration,
                supersedes=bool(context.supersedes_item_id),
                consulted_sources=len(set(context.consulted_context_item_ids)),
            )
            log_event(
                logger,
                "memento.context.publish.completed",
                outcome=outcome,
                duration_ms=round(duration * 1000, 3),
                context_kind=context.context_kind.value,
                item_id=result.item_id if result else None,
                consulted_source_count=len(set(context.consulted_context_item_ids)),
                error_code=None if result else outcome,
            )

    async def get_context(
        self,
        request: DevelopmentContextQuery,
        *,
        auth: AuthorizationContext | None = None,
    ) -> DevelopmentContextBundle:
        set_request_scope(
            project=request.project,
            repository=request.repository,
            work_item=request.work_item or "",
        )
        started = perf_counter()
        outcome = "internal_error"
        bundle: DevelopmentContextBundle | None = None
        try:
            bundle = await super().get_context(request, auth=auth)
            hit_count = sum(len(getattr(bundle, block)) for block in BLOCK_BY_KIND.values())
            outcome = "found" if hit_count else "empty"
            return bundle
        except SearchBackendError:
            outcome = "gbrain_error"
            raise
        except ValueError:
            outcome = "validation_error"
            raise
        finally:
            duration = perf_counter() - started
            block_counts = {
                block: len(getattr(bundle, block)) if bundle is not None else 0
                for block in BLOCK_BY_KIND.values()
            }
            hit_count = sum(block_counts.values())
            self.metrics.record_memento_search(
                outcome=outcome,
                project=request.project,
                duration_seconds=duration,
                hit_count=hit_count,
                block_counts=block_counts,
            )
            log_event(
                logger,
                "memento.context.search.completed",
                outcome=outcome,
                duration_ms=round(duration * 1000, 3),
                hit_count=hit_count,
                block_counts=block_counts,
                error_code=None if outcome in {"found", "empty"} else outcome,
            )
