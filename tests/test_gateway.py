from unittest.mock import AsyncMock
from uuid import uuid4

from app.models.payment import PaymentStatus
from app.services import gateway


async def test_gateway_success(monkeypatch) -> None:
    monkeypatch.setattr(gateway.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(gateway.random, "uniform", lambda _a, _b: 0)
    monkeypatch.setattr(gateway.random, "random", lambda: 0.1)
    status = await gateway.emulate_payment_processing(uuid4())
    assert status == PaymentStatus.SUCCEEDED


async def test_gateway_failure(monkeypatch) -> None:
    monkeypatch.setattr(gateway.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(gateway.random, "uniform", lambda _a, _b: 0)
    monkeypatch.setattr(gateway.random, "random", lambda: 0.95)
    status = await gateway.emulate_payment_processing(uuid4())
    assert status == PaymentStatus.FAILED
