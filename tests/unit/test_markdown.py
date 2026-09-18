from controllers.utils.BD.markdown import MarkdownItemRepository, slugify
from models.access import SectionRef
from models.enums import LibraryItemType
from models.library_item import Attachment, LibraryItem


def test_markdown_round_trip() -> None:
    item = LibraryItem(
        section=SectionRef.parse("research/main"),
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


def test_markdown_renders_image_attachment_and_round_trips() -> None:
    item = LibraryItem(
        section=SectionRef.parse("research/main"),
        type=LibraryItemType.EXPERIMENT_REPORT,
        title="Report",
        content="Results",
        attachments=[
            Attachment(
                id="upload_1",
                path="attachments/lib_1/chart.webp",
                sha256="a" * 64,
                mime_type="image/webp",
                size_bytes=42,
                original_name="chart.png",
            )
        ],
    )

    rendered = MarkdownItemRepository.render(item)

    assert "![[attachments/lib_1/chart.webp|chart.png]]" in rendered
