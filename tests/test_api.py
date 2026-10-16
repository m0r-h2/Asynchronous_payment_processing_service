import uuid

from httpx import AsyncClient

from tests.conftest import auth_headers


async def test_health_does_not_require_api_key(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_payment_requires_api_key(client: AsyncClient, payment_payload: dict) -> None:
    response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers={"Idempotency-Key": "k-1"},
    )
    assert response.status_code == 401


async def test_create_payment_rejects_wrong_api_key(
    client: AsyncClient, payment_payload: dict
) -> None:
    response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers={"X-API-Key": "wrong-key", "Idempotency-Key": "k-2"},
    )
    assert response.status_code == 401


async def test_create_payment_requires_idempotency_key(
    client: AsyncClient, payment_payload: dict
) -> None:
    response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers={"X-API-Key": "dev-api-key"},
    )
    assert response.status_code == 422


async def test_create_payment_returns_202(
    client: AsyncClient, payment_payload: dict
) -> None:
    response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers=auth_headers("order-202"),
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert uuid.UUID(body["payment_id"])
    assert "created_at" in body


async def test_idempotent_replay_returns_same_payment(
    client: AsyncClient, payment_payload: dict
) -> None:
    headers = auth_headers("order-dup")
    first = await client.post("/api/v1/payments", json=payment_payload, headers=headers)
    second = await client.post("/api/v1/payments", json=payment_payload, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["payment_id"] == second.json()["payment_id"]


async def test_idempotency_conflict_on_different_payload(
    client: AsyncClient, payment_payload: dict
) -> None:
    headers = auth_headers("order-conflict")
    first = await client.post("/api/v1/payments", json=payment_payload, headers=headers)
    assert first.status_code == 202

    changed = {**payment_payload, "amount": "50.00"}
    second = await client.post("/api/v1/payments", json=changed, headers=headers)
    assert second.status_code == 409


async def test_get_payment_returns_details(
    client: AsyncClient, payment_payload: dict
) -> None:
    created = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers=auth_headers("order-get"),
    )
    payment_id = created.json()["payment_id"]
    response = await client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"X-API-Key": "dev-api-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == payment_id
    assert body["amount"] == "199.90"
    assert body["currency"] == "RUB"
    assert body["status"] == "pending"
    assert body["idempotency_key"] == "order-get"
    assert body["metadata"] == {"order_id": "1001"}
    assert body["processed_at"] is None


async def test_get_unknown_payment_returns_404(client: AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/payments/{uuid.uuid4()}",
        headers={"X-API-Key": "dev-api-key"},
    )
    assert response.status_code == 404


async def test_invalid_currency_returns_422(client: AsyncClient, payment_payload: dict) -> None:
    payload = {**payment_payload, "currency": "GBP"}
    response = await client.post(
        "/api/v1/payments",
        json=payload,
        headers=auth_headers("order-gbp"),
    )
    assert response.status_code == 422
