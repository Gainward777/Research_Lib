from models.enums import LibraryItemType
from models.results import AnswerResult, SearchHit
from views.telegram.answer_view import render_answer


def test_answer_view_never_adds_its_own_sources() -> None:
    answer = "  Ответ GBrain.\n "
    result = AnswerResult(
        answer=answer,
        sources=[
            SearchHit(
                item_id="lib_1",
                slug="notes/one",
                type=LibraryItemType.NOTE,
                title="Источник",
            )
        ],
    )

    assert render_answer(result) == answer
