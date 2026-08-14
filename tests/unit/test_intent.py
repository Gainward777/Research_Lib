from controllers.utils.services.librarian.intent_service import Intent, classify_intent


def test_intent_router() -> None:
    assert classify_intent("/search LoRA") == Intent.SEARCH
    assert classify_intent("/ask Что известно?") == Intent.ASK
    assert classify_intent("Что известно о LoRA?") == Intent.ASK
    assert classify_intent("How does LoRA work?") == Intent.ASK
    assert classify_intent("Сохранить вопрос?") == Intent.SAVE
    assert classify_intent("Сохранить наблюдение") == Intent.SAVE
    assert classify_intent("Что на этом графике?", has_attachments=True) == Intent.SAVE
    assert classify_intent("Почему?", is_forwarded=True) == Intent.SAVE
    assert classify_intent("Отчёт: почему метрика упала?") == Intent.SAVE
