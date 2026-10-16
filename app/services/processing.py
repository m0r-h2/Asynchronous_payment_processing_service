import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import WebhookPayload
from app.services.gateway import emulate_payment_processing
from app.services.webhook import send_webhook

logger = logging.getLogger(__name__)


async def process_payment_event(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    payment_id: uuid.UUID,
) -> None:
    payment = await _get_for_update(session, payment_id)
    if payment is None:
        logger.error("Payment %s not found, dropping event", payment_id)
        await session.commit()
        return

    needs_gateway = payment.status == PaymentStatus.PENDING
    await session.commit()

    if needs_gateway:
        status = await emulate_payment_processing(payment_id)
        payment = await _get_for_update(session, payment_id)
        if payment is None:
            await session.commit()
            return
        if payment.status == PaymentStatus.PENDING:
            payment.status = status
            payment.processed_at = datetime.now(timezone.utc)
            logger.info("Payment %s processed with status %s", payment.id, status)
        await session.commit()

    payment = await _get_for_update(session, payment_id)
    if payment is None or payment.webhook_sent_at is not None:
        await session.commit()
        return

    payload = WebhookPayload(
        payment_id=payment.id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.extra_metadata,
        processed_at=payment.processed_at,
    )
    webhook_url = payment.webhook_url
    await session.commit()

    await send_webhook(http_client, webhook_url, payload)

    payment = await _get_for_update(session, payment_id)
    if payment is not None and payment.webhook_sent_at is None:
        payment.webhook_sent_at = datetime.now(timezone.utc)
    await session.commit()


async def _get_for_update(session: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    result = await session.execute(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    )
    return result.scalar_one_or_none()
