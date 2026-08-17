from models.enums import LibraryItemType

REPORT_PREFIXES = ("отчёт", "отчет", "report", "результаты эксперимента")
REPORT_SECTIONS = (
    "цель",
    "метод",
    "ход работы",
    "результат",
    "вывод",
    "метрики",
    "гипотеза",
)


def classify_material(text: str) -> LibraryItemType:
    lowered = text.strip().casefold()
    if "doi.org/" in lowered or "arxiv.org/" in lowered:
        return LibraryItemType.PUBLICATION
    if lowered.startswith("идея:") or lowered.startswith("idea:"):
        return LibraryItemType.IDEA
    if lowered.startswith(REPORT_PREFIXES):
        return LibraryItemType.EXPERIMENT_REPORT
    section_count = sum(
        marker in lowered for marker in (f"{section}:" for section in REPORT_SECTIONS)
    )
    if section_count >= 2:
        return LibraryItemType.EXPERIMENT_REPORT
    return LibraryItemType.NOTE
