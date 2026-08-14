from models.library_item import LibraryItem


def render_item(item: LibraryItem) -> str:
    return f"{item.title}\n\n{item.summary or item.content}\n\nID: {item.id}"
