from models.results import SearchHit


def render_search(hits: list[SearchHit]) -> dict[str, object]:
    return {"hits": [hit.model_dump(mode="json") for hit in hits]}
