from models.results import AnswerResult


def render_answer(result: AnswerResult) -> str:
    sources = "\n".join(f"- {item.title} ({item.item_id})" for item in result.sources)
    return result.answer + (f"\n\nИсточники:\n{sources}" if sources else "")
