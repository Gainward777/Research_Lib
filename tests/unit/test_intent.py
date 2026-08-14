from controllers.utils.services.librarian.intent_service import Intent, classify_intent


def test_intent_router() -> None:
    assert classify_intent("/search LoRA") == Intent.SEARCH
    assert classify_intent("Что известно?") == Intent.ASK
    assert classify_intent("Сохранить наблюдение") == Intent.SAVE
