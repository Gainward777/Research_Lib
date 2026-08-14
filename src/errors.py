class ResearchLibraryError(Exception):
    """Base application error."""


class NotFoundError(ResearchLibraryError):
    pass


class IdempotencyConflictError(ResearchLibraryError):
    pass


class ValidationError(ResearchLibraryError):
    pass


class StorageError(ResearchLibraryError):
    pass


class SearchBackendError(ResearchLibraryError):
    pass
