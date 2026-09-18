from io import BytesIO

from PIL import Image


def create_png() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (32, 16), "red").save(stream, format="PNG")
    return stream.getvalue()


def create_item(client, auth_headers, key: str, title: str) -> dict[str, object]:
    response = client.post(
        "/v1/items",
        headers={**auth_headers, "Idempotency-Key": key},
        json={"type": "note", "title": title, "content": title},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_upload_is_attached_to_item(client, auth_headers) -> None:
    uploaded = client.post(
        "/v1/uploads",
        headers=auth_headers,
        files={"file": ("sample.png", create_png(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    upload = uploaded.json()
    assert upload["mime_type"] == "image/webp"

    created = client.post(
        "/v1/items",
        headers={**auth_headers, "Idempotency-Key": "upload:item:1"},
        json={
            "type": "note",
            "title": "Item with image",
            "attachment_upload_ids": [upload["upload_id"]],
        },
    )
    assert created.status_code == 200, created.text

    fetched = client.get(f"/v1/items/{created.json()['item_id']}", headers=auth_headers)
    attachments = fetched.json()["item"]["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["mime_type"] == "image/webp"

    downloaded = client.get(
        f"/v1/attachments/{attachments[0]['id']}", headers=auth_headers
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "image/webp"
    assert downloaded.content


def test_relation_and_schema_proposal_workflows(client, auth_headers) -> None:
    source = create_item(client, auth_headers, "relation:source", "Source")
    target = create_item(client, auth_headers, "relation:target", "Target")

    relation = client.post(
        f"/v1/items/{source['item_id']}/relations",
        headers=auth_headers,
        json={"type": "related-to", "target_id": target["item_id"]},
    )
    assert relation.status_code == 200, relation.text
    assert relation.json()["related_count"] == 1

    proposal = client.post(
        "/v1/schema/proposals",
        headers=auth_headers,
        json={"kind": "relation", "name": "extends", "payload": {"inverse": "extended-by"}},
    )
    assert proposal.status_code == 200, proposal.text
    proposal_id = proposal.json()["id"]

    listed = client.get("/v1/schema/proposals", headers=auth_headers)
    assert any(item["id"] == proposal_id for item in listed.json())

    applied = client.post(f"/v1/schema/proposals/{proposal_id}/apply", headers=auth_headers)
    assert applied.status_code == 200
    assert applied.json()["status"] == "applied"
