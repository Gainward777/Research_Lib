from models.results import SaveResult


def render_saved(result: SaveResult, title: str) -> str:
    index_status = "проиндексировано" if result.indexed else "ожидает индексации"
    return f"Сохранено: {title}\nID: {result.item_id}\nСтатус: {index_status}"
