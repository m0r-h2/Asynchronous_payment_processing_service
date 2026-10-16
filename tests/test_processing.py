from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentStatus
from app.services import processing
from app.services.payment import create_payment
from tests.conftest import make_create_payload


async def test_process_pending_payment_updates_status_and_sends_webhook(
    session: AsyncSession, monkeypatch
) -> None:
    payment, _ = await create_payment(session, make_create_payload(), "proc-ok")
    monkeypatch.setattr(
        processing,
        "emulate_payment_processing",
        AsyncMock(return_value=PaymentStatus.SUCCEEDED),
    )
    monkeypatch.setattr(processing, "send_webhook", AsyncMock())

    async with httpx.AsyncClient() as client:
        await processing.process_payment_event(session, client, payment.id)

    await session.refresh(payment)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.processed_at is not None
    assert payment.webhook_sent_at is not None
    processing.send_webhook.assert_awaited_once()


async def test_process_skips_gateway_if_already_terminal(session: AsyncSession, monkeypatch) -> None:
    payment, _ = await create_payment(session, make_create_payload(), "proc-skip")
    payment.status = PaymentStatus.FAILED
    payment.processed_at = datetime.now(timezone.utc)
    await session.commit()

    gateway = AsyncMock()
    monkeypatch.setattr(processing, "emulate_payment_processing", gateway)
    monkeypatch.setattr(processing, "send_webhook", AsyncMock())

    async with httpx.AsyncClient() as client:
        await processing.process_payment_event(session, client, payment.id)

    gateway.assert_not_awaited()
    processing.send_webhook.assert_awaited_once()
    await session.refresh(payment)
    assert payment.status == PaymentStatus.FAILED
    assert payment.webhook_sent_at is not None


async def test_process_skips_webhook_if_already_sent(session: AsyncSession, monkeypatch) -> None:
    payment, _ = await create_payment(session, make_create_payload(), "proc-hooked")
    payment.status = PaymentStatus.SUCCEEDED
    payment.processed_at = datetime.now(timezone.utc)
    payment.webhook_sent_at = datetime.now(timezone.utc)
    await session.commit()

    monkeypatch.setattr(processing, "emulate_payment_processing", AsyncMock())
    webhook = AsyncMock()
    monkeypatch.setattr(processing, "send_webhook", webhook)

    async with httpx.AsyncClient() as client:
        await processing.process_payment_event(session, client, payment.id)

    webhook.assert_not_awaited()


async def test_process_unknown_payment_is_dropped(session: AsyncSession, monkeypatch) -> None:
    from uuid import uuid4

    gateway = AsyncMock()
    monkeypatch.setattr(processing, "emulate_payment_processing", gateway)
    async with httpx.AsyncClient() as client:
        await processing.process_payment_event(session, client, uuid4())
    gateway.assert_not_awaited()
