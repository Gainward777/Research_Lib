import re

from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from models.commands import SearchCommand
from models.results import AnswerResult, SearchHit


class FakeGBrainAdapter(GBrainAdapter):
    """Test-only in-memory substitute; production never constructs this class."""

    def __init__(self, repository) -> None:
        self.repository = repository

    async def initialize(self) -> bool:
        return False

    def mark_bootstrap_complete(self) -> None:
        return None

    async def health(self) -> bool:
        return True

    async def index(self, _item) -> None:
        return None

    async def search(self, command: SearchCommand) -> list[SearchHit]:
        terms = set(re.findall(r"[\w-]+", command.query.casefold()))
        allowed_types = set(command.types)
        required_tags = {tag.casefold() for tag in command.tags}
        hits: list[SearchHit] = []
        for page in self.repository.iter_pages():
            item = self.repository.parse(page.read_text(encoding="utf-8"))
            if allowed_types and item.type not in allowed_types:
                continue
            item_tags = {tag.casefold() for tag in item.tags}
            if required_tags and not required_tags.issubset(item_tags):
                continue
            haystack = " ".join(
                [item.title, item.summary, item.content, " ".join(item.tags)]
            ).casefold()
            matched = sum(1 for term in terms if term in haystack)
            if not matched:
                continue
            relative = page.relative_to(self.repository.brain_root).with_suffix("").as_posix()
            hits.append(
                SearchHit(
                    item_id=item.id,
                    slug=relative,
                    type=item.type,
                    title=item.title,
                    summary=item.summary,
                    score=matched / max(len(terms), 1),
                    tags=item.tags,
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.title.casefold()))
        return hits[: command.limit]

    async def query(self, command: SearchCommand) -> list[SearchHit]:
        return await self.search(command)

    async def think(self, command: SearchCommand) -> AnswerResult:
        hits = await self.search(command)
        if not hits:
            return AnswerResult(answer="No relevant material was found.")
        return AnswerResult(answer="Answer synthesized from the library.", sources=hits)
