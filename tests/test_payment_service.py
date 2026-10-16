from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxMessage
from app.models.payment import Payment, PaymentStatus
from app.services.payment import IdempotencyConflictError, create_payment, get_payment
from tests.conftest import make_create_payload


async def test_create_payment_writes_outbox_in_same_commit(session: AsyncSession) -> None:
    payload = make_create_payload()
    payment, created = await create_payment(session, payload, "key-outbox")
    assert created is True
    assert payment.status == PaymentStatus.PENDING

    payments_count = await session.scalar(select(func.count()).select_from(Payment))
    outbox_count = await session.scalar(select(func.count()).select_from(OutboxMessage))
    assert payments_count == 1
    assert outbox_count == 1

    event = (await session.execute(select(OutboxMessage))).scalar_one()
    assert event.event_type == "payments.new"
    assert event.published_at is None
    assert event.payload["payment_id"] == str(payment.id)
    assert event.aggregate_id == payment.id


async def test_create_payment_replay_does_not_duplicate_outbox(session: AsyncSession) -> None:
    payload = make_create_payload()
    first, created_first = await create_payment(session, payload, "key-replay")
    second, created_second = await create_payment(session, payload, "key-replay")
    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    outbox_count = await session.scalar(select(func.count()).select_from(OutboxMessage))
    assert outbox_count == 1


async def test_create_payment_conflict(session: AsyncSession) -> None:
    await create_payment(session, make_create_payload(amount="10.00"), "key-conflict")
    try:
        await create_payment(session, make_create_payload(amount="11.00"), "key-conflict")
        raise AssertionError("expected IdempotencyConflictError")
    except IdempotencyConflictError as exc:
        assert "key-conflict" in str(exc)


async def test_get_payment(session: AsyncSession) -> None:
    payment, _ = await create_payment(session, make_create_payload(), "key-get")
    loaded = await get_payment(session, payment.id)
    assert loaded is not None
    assert loaded.id == payment.id
    assert loaded.idempotency_key == "key-get"
    assert await get_payment(session, payment.id) is not None
