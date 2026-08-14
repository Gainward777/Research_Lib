from controllers.utils.BD.receipts import payload_hash


def test_payload_hash_is_order_independent() -> None:
    assert payload_hash({"a": 1, "b": 2}) == payload_hash({"b": 2, "a": 1})
