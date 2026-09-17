from enum import StrEnum


class LibraryItemType(StrEnum):
    EXPERIMENT = "experiment"
    EXPERIMENT_REPORT = "experiment-report"
    IDEA = "idea"
    PUBLICATION = "publication"
    METHOD = "method"
    CONCEPT = "concept"
    MODEL = "model"
    DATASET = "dataset"
    SOURCE = "source"
    NOTE = "note"
    DEVELOPMENT_CONTEXT = "development-context"


class SourceKind(StrEnum):
    TELEGRAM = "telegram"
    AUTORESEARCH = "autoresearch"
    API = "api"
    MANUAL = "manual"
    AGENT = "agent"


class RelationType(StrEnum):
    TESTS = "tests"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MOTIVATED_BY = "motivated-by"
    DERIVED_FROM = "derived-from"
    USES_METHOD = "uses-method"
    USES_MODEL = "uses-model"
    USES_DATASET = "uses-dataset"
    DESCRIBED_BY = "described-by"
    PRODUCED = "produced"
    CONTINUES = "continues"
    RELATED_TO = "related-to"
    HAS_SOURCE = "has-source"


class IngestStatus(StrEnum):
    RECEIVED = "received"
    DOWNLOADING = "downloading"
    STORED_RAW = "stored_raw"
    CLASSIFYING = "classifying"
    WRITING_PAGE = "writing_page"
    INDEXING = "indexing"
    PENDING_INDEX = "pending_index"
    COMPLETED = "completed"
    RETRYABLE_FAILED = "retryable_failed"
    PERMANENTLY_FAILED = "permanently_failed"
