from models.results import SearchHit


def render_search(hits: list[SearchHit]) -> str:
    if not hits:
        return "Ничего не найдено."
    return "\n\n".join(
        f"{index}. {hit.title}\n{hit.summary or hit.slug}\nID: {hit.item_id}"
        for index, hit in enumerate(hits, start=1)
    )
