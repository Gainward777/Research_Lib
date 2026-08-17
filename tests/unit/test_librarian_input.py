from controllers.utils.services.ingestion.classifier import classify_material
from models.enums import LibraryItemType
from views.telegram.message_view import split_message


def test_report_classification_accepts_free_form_sections() -> None:
    assert (
        classify_material("Отчёт по обучению\nКачество выросло")
        is LibraryItemType.EXPERIMENT_REPORT
    )
    assert (
        classify_material("Гипотеза: новый scheduler\nМетод: A/B\nВывод: стало лучше")
        is LibraryItemType.EXPERIMENT_REPORT
    )


def test_long_telegram_answer_is_split_without_data_loss() -> None:
    text = ("paragraph of evidence\n\n" * 300).strip()
    chunks = split_message(text, limit=200)

    assert all(len(chunk) <= 200 for chunk in chunks)
    assert "".join(chunks) == text
