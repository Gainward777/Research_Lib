from controllers.utils.services.library.item_service import ItemService
from models.library_item import Relation


class RelationService:
    def __init__(self, items: ItemService) -> None:
        self.items = items

    async def add(self, source_id: str, relation: Relation):
        return await self.items.add_relation(source_id, relation)
