import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import OutboxMessage
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentCreate


class IdempotencyConflictError(Exception):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Idempotency-Key '{idempotency_key}' already used with a different payload"
        )
        self.idempotency_key = idempotency_key


async def create_payment(
    session: AsyncSession,
    payload: PaymentCreate,
    idempotency_key: str,
) -> tuple[Payment, bool]:
    request_hash = payload.fingerprint()
    existing = await _get_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(idempotency_key)
        return existing, False

    payment = Payment(
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        extra_metadata=payload.metadata,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        webhook_url=str(payload.webhook_url),
    )
    session.add(payment)
    await session.flush()
    session.add(
        OutboxMessage(
            aggregate_id=payment.id,
            event_type="payments.new",
            payload={"payment_id": str(payment.id), "event_type": "payments.new"},
        )
    )

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await _get_by_idempotency_key(session, idempotency_key)
        if existing is None:
            raise
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(idempotency_key) from None
        return existing, False

    await session.refresh(payment)
    return payment, True


async def get_payment(session: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    return await session.get(Payment, payment_id)


async def _get_by_idempotency_key(session: AsyncSession, key: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.idempotency_key == key))
    return result.scalar_one_or_none()
