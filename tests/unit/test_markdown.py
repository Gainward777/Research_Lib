from controllers.utils.BD.markdown import MarkdownItemRepository, slugify
from models.enums import LibraryItemType
from models.library_item import LibraryItem


def test_markdown_round_trip() -> None:
    item = LibraryItem(
        type=LibraryItemType.IDEA,
        title="Новая идея",
        summary="Краткое резюме",
        content="Полное содержание",
        tags=["research"],
    )

    rendered = MarkdownItemRepository.render(item)
    restored = MarkdownItemRepository.parse(rendered)

    assert restored == item


def test_slugify_falls_back_for_non_ascii_title() -> None:
    assert slugify("Только кириллица") == "item"
