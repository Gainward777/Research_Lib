def test_health_and_readiness(client) -> None:
    assert client.get("/healthz").json()["status"] == "ok"
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_get_search_and_idempotency(client, auth_headers) -> None:
    headers = {**auth_headers, "Idempotency-Key": "test:item:1"}
    payload = {
        "type": "idea",
        "title": "LoRA rank experiment",
        "summary": "Rank 32 overfits earlier than rank 16.",
        "content": "Compare ranks 8, 16 and 32 on SDXL.",
        "tags": ["lora", "sdxl"],
    }

    created = client.post("/v1/items", json=payload, headers=headers)
    assert created.status_code == 200, created.text
    first = created.json()
    assert first["created"] is True
    assert first["indexed"] is True

    repeated = client.post("/v1/items", json=payload, headers=headers)
    assert repeated.status_code == 200
    assert repeated.json() == first

    fetched = client.get(f"/v1/items/{first['item_id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["item"]["title"] == payload["title"]

    search = client.post("/v1/search", json={"query": "SDXL overfits"}, headers=auth_headers)
    assert search.status_code == 200
    assert search.json()["hits"][0]["item_id"] == first["item_id"]


def test_idempotency_conflict(client, auth_headers) -> None:
    headers = {**auth_headers, "Idempotency-Key": "test:conflict:1"}
    first = {"type": "note", "title": "First"}
    second = {"type": "note", "title": "Second"}

    assert client.post("/v1/items", json=first, headers=headers).status_code == 200
    conflict = client.post("/v1/items", json=second, headers=headers)

    assert conflict.status_code == 409
    assert conflict.json()["error"] == "idempotency_conflict"


def test_experiment_report_contract(client, auth_headers) -> None:
    headers = {**auth_headers, "Idempotency-Key": "autoresearch:exp-1:iter-2:1"}
    response = client.post(
        "/v1/experiment-reports",
        headers=headers,
        json={
            "experiment_external_id": "exp-1",
            "iteration_external_id": "iter-2",
            "report_version": 1,
            "title": "Rank comparison",
            "summary": "Rank 16 is the best compromise.",
            "conclusions": ["Rank 32 overfits earlier."],
            "configuration": {"base_model": "SDXL", "steps": 500},
            "metrics_summary": {"best_loss": 0.091},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["slug"].startswith("reports/")


def test_auth_is_required(client) -> None:
    response = client.post("/v1/search", json={"query": "anything"})
    assert response.status_code == 401

    unrelated_token = client.post(
        "/v1/search",
        json={"query": "anything"},
        headers={"Authorization": "Bearer unrelated-token"},
    )
    assert unrelated_token.status_code == 401
