from models.results import SearchHit
from views.api.responses import SearchResponse


def render_search(hits: list[SearchHit]) -> SearchResponse:
    return SearchResponse(hits=hits)
