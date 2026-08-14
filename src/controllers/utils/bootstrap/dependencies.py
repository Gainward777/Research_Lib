from dataclasses import dataclass

from controllers.utils.BD.attachments import AttachmentStore
from controllers.utils.BD.jobs import JobStore
from controllers.utils.BD.markdown import MarkdownItemRepository
from controllers.utils.BD.migrations import apply_migrations
from controllers.utils.BD.receipts import ReceiptStore
from controllers.utils.BD.sqlite import Database
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from controllers.utils.infrastructure.gbrain.schema_installer import install_research_schema
from controllers.utils.services.ingestion.ingestion_service import IngestionService
from controllers.utils.services.ingestion.job_service import JobService
from controllers.utils.services.librarian.search_service import SearchService
from controllers.utils.services.library.idea_service import IdeaService
from controllers.utils.services.library.item_service import ItemService
from controllers.utils.services.library.publication_service import PublicationService
from controllers.utils.services.library.relation_service import RelationService
from controllers.utils.services.library.report_service import ReportService
from controllers.utils.services.schema.proposal_service import ProposalService


@dataclass
class ApplicationContainer:
    settings: Settings
    database: Database
    repository: MarkdownItemRepository
    attachments: AttachmentStore
    gbrain: GBrainAdapter
    items: ItemService
    reports: ReportService
    ideas: IdeaService
    publications: PublicationService
    relations: RelationService
    search: SearchService
    jobs: JobService
    proposals: ProposalService
    ingestion: IngestionService

    async def close(self) -> None:
        await self.database.close()


async def build_container(settings: Settings | None = None) -> ApplicationContainer:
    settings = settings or Settings()
    settings.ensure_directories()
    install_research_schema(settings.library_brain_root)
    database = Database(settings.library_sqlite_path)
    await database.connect()
    await apply_migrations(database)

    repository = MarkdownItemRepository(settings.library_brain_root, database)
    await repository.rebuild_catalog()
    attachments = AttachmentStore(
        settings.library_attachments_root,
        database,
        max_long_side=settings.library_image_max_long_side_px,
        image_format=settings.library_image_format,
        image_quality=settings.library_image_quality,
    )
    receipts = ReceiptStore(database)
    jobs_store = JobStore(database)
    gbrain = GBrainAdapter(
        repository,
        mode=settings.library_gbrain_mode,
        command=settings.library_gbrain_command,
        timeout_seconds=settings.library_gbrain_timeout_seconds,
        home=settings.library_gbrain_home,
    )
    items = ItemService(repository, attachments, receipts, jobs_store, gbrain)
    return ApplicationContainer(
        settings=settings,
        database=database,
        repository=repository,
        attachments=attachments,
        gbrain=gbrain,
        items=items,
        reports=ReportService(items),
        ideas=IdeaService(items),
        publications=PublicationService(items),
        relations=RelationService(items),
        search=SearchService(gbrain),
        jobs=JobService(jobs_store),
        proposals=ProposalService(database, settings.library_schema_mutation_mode),
        ingestion=IngestionService(items),
    )
