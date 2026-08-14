from controllers.utils.services.library.item_service import ItemService
from models.commands import CreateItemCommand
from models.enums import LibraryItemType, SourceKind
from models.experiment_report import ExperimentReport
from models.results import SaveResult


class ReportService:
    def __init__(self, items: ItemService) -> None:
        self.items = items

    async def save(
        self,
        report: ExperimentReport,
        *,
        attachment_upload_ids: list[str],
        idempotency_key: str,
    ) -> SaveResult:
        content_parts = []
        if report.hypothesis:
            content_parts.append(f"## Гипотеза\n\n{report.hypothesis}")
        if report.conclusions:
            content_parts.append(
                "## Выводы\n\n" + "\n".join(f"- {item}" for item in report.conclusions)
            )
        if report.limitations:
            content_parts.append(
                "## Ограничения\n\n" + "\n".join(f"- {item}" for item in report.limitations)
            )
        command = CreateItemCommand(
            type=LibraryItemType.EXPERIMENT_REPORT,
            title=report.title,
            content="\n\n".join(content_parts),
            summary=report.summary,
            source_kind=SourceKind.AUTORESEARCH,
            source_external_id=(
                f"autoresearch:{report.experiment_external_id}:{report.iteration_external_id}"
            ),
            attachment_upload_ids=attachment_upload_ids,
            metadata=report.model_dump(mode="json"),
        )
        return await self.items.create(command, idempotency_key=idempotency_key)
