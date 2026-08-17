from models.results import AnswerResult


def render_answer(result: AnswerResult) -> str:
    return result.answer
