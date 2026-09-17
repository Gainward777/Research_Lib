from models.memento import DevelopmentContextBundle
from models.results import SaveResult


def render_context_bundle(bundle: DevelopmentContextBundle) -> dict[str, object]:
    return bundle.model_dump(mode="json")


def render_context_receipt(result: SaveResult) -> dict[str, object]:
    return result.model_dump(mode="json")
