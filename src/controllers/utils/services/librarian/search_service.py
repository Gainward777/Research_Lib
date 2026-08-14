from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter
from models.commands import SearchCommand
from models.results import AnswerResult, SearchHit


class SearchService:
    def __init__(self, gbrain: GBrainAdapter) -> None:
        self.gbrain = gbrain

    async def search(self, command: SearchCommand) -> list[SearchHit]:
        return await self.gbrain.search(command)

    async def ask(self, command: SearchCommand) -> AnswerResult:
        return await self.gbrain.ask(command)
