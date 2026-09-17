from models.enums import LibraryItemType
from models.results import AnswerResult, SearchHit
from views.telegram.answer_view import render_answer
from views.telegram.error_view import render_error


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


def test_error_view_never_exposes_english_internal_error() -> None:
    response = render_error("OpenAI router returned no structured decision")

    assert response == "Не удалось выполнить запрос. Попробуйте ещё раз позже."
