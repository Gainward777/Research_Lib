from controllers.utils.infrastructure.gbrain.adapter import GBrainAdapter


def test_gbrain_result_normalization() -> None:
    hits = GBrainAdapter._normalize_hits(
        {
            "data": {
                "results": [
                    {
                        "slug": "ideas/example",
                        "frontmatter": {
                            "id": "lib_example",
                            "type": "idea",
                            "title": "Example",
                            "tags": ["test"],
                        },
                        "snippet": "Relevant text",
                        "score": 0.75,
                    }
                ]
            }
        },
        10,
    )

    assert hits[0].item_id == "lib_example"
    assert hits[0].slug == "ideas/example"
    assert hits[0].score == 0.75


def test_gbrain_environment_allowlist_contains_no_tokens() -> None:
    assert all(
        "TOKEN" not in name and "KEY" not in name for name in GBrainAdapter.SAFE_ENVIRONMENT_NAMES
    )
