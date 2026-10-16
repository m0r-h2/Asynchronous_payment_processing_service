import logging

from faststream import Logger
from faststream.rabbit import RabbitMessage

from app.broker.rabbit import broker
from app.broker.topology import (
    MAX_PROCESSING_ATTEMPTS,
    new_queue,
    payments_exchange,
    retry_exchange,
    retry_routing_key,
)
from app.db import async_session_factory
from app.http_client import http_client
from app.schemas.payment import PaymentNewEvent
from app.services.processing import process_payment_event

logger = logging.getLogger(__name__)

RETRY_HEADER = "x-retry-count"


def _retry_count(message: RabbitMessage) -> int:
    headers = message.headers or {}
    raw = headers.get(RETRY_HEADER, 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


@broker.subscriber(
    new_queue,
    exchange=payments_exchange,
    no_ack=True,
)
async def handle_new_payment(
    event: PaymentNewEvent,
    message: RabbitMessage,
    log: Logger,
) -> None:
    retries = _retry_count(message)
    log.info("Processing payment %s (attempt %s)", event.payment_id, retries + 1)

    try:
        async with async_session_factory() as session:
            await process_payment_event(session, http_client, event.payment_id)
        await message.ack()
    except Exception:
        logger.exception("Failed to process payment %s", event.payment_id)
        if retries + 1 >= MAX_PROCESSING_ATTEMPTS:
            log.error(
                "Payment %s exceeded %s attempts, sending to DLQ",
                event.payment_id,
                MAX_PROCESSING_ATTEMPTS,
            )
            await message.reject(requeue=False)
            return

        next_attempt = retries + 1
        await broker.publish(
            event,
            exchange=retry_exchange,
            routing_key=retry_routing_key(next_attempt),
            persist=True,
            headers={RETRY_HEADER: str(next_attempt)},
        )
        log.warning(
            "Payment %s scheduled for retry %s",
            event.payment_id,
            next_attempt,
        )
        await message.ack()

