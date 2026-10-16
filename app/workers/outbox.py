import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.broker.rabbit import broker
from app.broker.topology import NEW_ROUTING_KEY, payments_exchange
from app.config import settings
from app.db import async_session_factory
from app.models.outbox import OutboxMessage

logger = logging.getLogger(__name__)


async def publish_outbox_batch() -> int:
    async with async_session_factory() as session:
        result = await session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.published_at.is_(None))
            .order_by(OutboxMessage.created_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
        messages = list(result.scalars().all())
        if not messages:
            await session.commit()
            return 0

        published = 0
        for message in messages:
            try:
                await broker.publish(
                    message.payload,
                    exchange=payments_exchange,
                    routing_key=NEW_ROUTING_KEY,
                    persist=True,
                )
                message.published_at = datetime.now(timezone.utc)
                published += 1
            except Exception:
                logger.exception("Failed to publish outbox message %s", message.id)

        await session.commit()
        return published


async def run_outbox_publisher() -> None:
    logger.info("Outbox publisher started")
    while True:
        try:
            published = await publish_outbox_batch()
            if published:
                logger.info("Published %s outbox event(s)", published)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Outbox publisher iteration failed")
        await asyncio.sleep(settings.outbox_poll_interval_sec)
