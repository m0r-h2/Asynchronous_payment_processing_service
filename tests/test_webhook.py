from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.models.payment import Currency, PaymentStatus
from app.schemas.payment import WebhookPayload
from app.services import webhook as webhook_module
from app.services.webhook import send_webhook


def _payload() -> WebhookPayload:
    return WebhookPayload(
        payment_id=uuid4(),
        status=PaymentStatus.SUCCEEDED,
        amount=Decimal("10.00"),
        currency=Currency.USD,
        description="Hook",
        metadata={},
        processed_at=datetime.now(timezone.utc),
    )


async def test_send_webhook_retries_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(webhook_module.asyncio, "sleep", AsyncMock())
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(500, text="down")
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await send_webhook(client, "http://example.com/hook", _payload())
    assert attempts["n"] == 3


async def test_send_webhook_raises_after_three_failures(monkeypatch) -> None:
    monkeypatch.setattr(webhook_module.asyncio, "sleep", AsyncMock())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await send_webhook(client, "http://example.com/hook", _payload())
