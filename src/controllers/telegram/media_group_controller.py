from collections import defaultdict

from aiogram.types import Message


class MediaGroupCollector:
    def __init__(self) -> None:
        self.groups: dict[str, list[Message]] = defaultdict(list)

    def add(self, message: Message) -> list[Message]:
        if not message.media_group_id:
            return [message]
        self.groups[message.media_group_id].append(message)
        return list(self.groups[message.media_group_id])

    def pop(self, media_group_id: str) -> list[Message]:
        return self.groups.pop(media_group_id, [])
