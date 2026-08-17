from collections.abc import Callable
from dataclasses import dataclass

from controllers.utils.BD.attachments import AttachmentStore
from controllers.utils.BD.collections import CollectionStore
from controllers.utils.BD.jobs import JobStore
from controllers.utils.BD.markdown import MarkdownItemRepository
from controllers.utils.BD.migrations import apply_migrations
from controllers.utils.BD.receipts import ReceiptStore
from controllers.utils.BD.sqlite import Database
from controllers.utils.bootstrap.settings import Settings
from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from controllers.utils.infrastructure.gbrain.schema_installer import install_research_schema
from controllers.utils.infrastructure.llm.openai_responses import OpenAIResponsesClient
from controllers.utils.services.ingestion.ingestion_service import IngestionService
from controllers.utils.services.ingestion.job_service import JobService
from controllers.utils.services.librarian.dialog_context import DialogContextStore
from controllers.utils.services.librarian.search_service import SearchService
from controllers.utils.services.library.idea_service import IdeaService
from controllers.utils.services.library.item_service import ItemService
from controllers.utils.services.library.publication_service import PublicationService
from controllers.utils.services.library.relation_service import RelationService
from controllers.utils.services.library.report_service import ReportService
from controllers.utils.services.schema.proposal_service import ProposalService
from controllers.utils.skills.library import build_library_skill_registry
from controllers.utils.skills.registry import SkillRegistry
from controllers.utils.skills.router import NaturalLanguageRouter

GBrainFactory = Callable[[MarkdownItemRepository], GBrainAdapter]


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

    collections: CollectionStore
    dialog_context: DialogContextStore
    skills: SkillRegistry
    router: NaturalLanguageRouter

    async def close(self) -> None:
        await self.database.close()


async def build_container(
    settings: Settings | None = None,
    *,
    gbrain_factory: GBrainFactory | None = None,
) -> ApplicationContainer:
    settings = settings or Settings()
    settings.ensure_directories()
    install_research_schema(settings.library_brain_root)
    database = Database(settings.library_sqlite_path)
    await database.connect()
    try:
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
        if gbrain_factory is None:
            gbrain = GBrainAdapter(
                repository,
                command=settings.library_gbrain_command,
                timeout_seconds=settings.library_gbrain_timeout_seconds,
                home=settings.library_gbrain_home,
                expected_version=settings.library_gbrain_version,
                no_embedding=settings.library_gbrain_no_embedding,
                embedding_model=settings.library_gbrain_embedding_model,
                embedding_dimensions=settings.library_gbrain_embedding_dimensions,
                think_model=settings.library_gbrain_think_model,
            )
        else:
            gbrain = gbrain_factory(repository)

        gbrain_rebuild_required = await gbrain.initialize()
        if gbrain_rebuild_required:
            for page in repository.iter_pages():
                item = repository.parse(page.read_text(encoding="utf-8"))
                await gbrain.index(item)
                await repository.mark_indexed(item.id)
            gbrain.mark_bootstrap_complete()

        items = ItemService(repository, attachments, receipts, jobs_store, gbrain)
        skills = build_library_skill_registry()
        collections = CollectionStore(database)
        dialog_context = DialogContextStore(settings.library_router_context_turns)
        router = NaturalLanguageRouter(
            OpenAIResponsesClient(
                settings.openai_api_key.get_secret_value(),
                model=settings.library_router_model,
                timeout_seconds=settings.library_router_timeout_seconds,
            ),
            skills,
        )
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
            collections=collections,
            dialog_context=dialog_context,
            skills=skills,
            router=router,
        )
    except Exception:
        await database.close()
        raise
