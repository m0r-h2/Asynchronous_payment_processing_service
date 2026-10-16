import asyncio
import logging

from aio_pika import ExchangeType as AioExchangeType
from aio_pika import connect_robust
from faststream.rabbit import Channel, RabbitBroker

from app.broker.topology import (
    DLQ_NAME,
    DLX_NAME,
    NEW_QUEUE_NAME,
    NEW_ROUTING_KEY,
    PAYMENTS_EXCHANGE_NAME,
    RETRY_EXCHANGE_NAME,
    RETRY_TTL_MS,
    retry_routing_key,
)
from app.config import settings

logger = logging.getLogger(__name__)

broker = RabbitBroker(
    settings.rabbitmq_url,
    default_channel=Channel(prefetch_count=1),
)


async def declare_topology(retries: int = 30) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            await _declare_topology()
            return
        except Exception as exc:
            last_error = exc
            logger.warning("RabbitMQ topology not ready (attempt %s/%s): %s", attempt, retries, exc)
            await asyncio.sleep(1)
    assert last_error is not None
    raise last_error


async def _declare_topology() -> None:
    connection = await connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()

        payments_ex = await channel.declare_exchange(
            PAYMENTS_EXCHANGE_NAME, AioExchangeType.DIRECT, durable=True
        )
        retry_ex = await channel.declare_exchange(
            RETRY_EXCHANGE_NAME, AioExchangeType.DIRECT, durable=True
        )
        dlx = await channel.declare_exchange(DLX_NAME, AioExchangeType.DIRECT, durable=True)

        new_q = await channel.declare_queue(
            NEW_QUEUE_NAME,
            durable=True,
            arguments={
                "x-queue-type": "classic",
                "x-dead-letter-exchange": DLX_NAME,
                "x-dead-letter-routing-key": DLQ_NAME,
            },
        )
        await new_q.bind(payments_ex, routing_key=NEW_ROUTING_KEY)

        dead_q = await channel.declare_queue(
            DLQ_NAME,
            durable=True,
            arguments={"x-queue-type": "classic"},
        )
        await dead_q.bind(dlx, routing_key=DLQ_NAME)

        for attempt, ttl in RETRY_TTL_MS.items():
            wait_q = await channel.declare_queue(
                f"payments.retry.{attempt}",
                durable=True,
                arguments={
                    "x-queue-type": "classic",
                    "x-message-ttl": ttl,
                    "x-dead-letter-exchange": PAYMENTS_EXCHANGE_NAME,
                    "x-dead-letter-routing-key": NEW_ROUTING_KEY,
                },
            )
            await wait_q.bind(retry_ex, routing_key=retry_routing_key(attempt))
