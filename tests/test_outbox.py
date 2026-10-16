from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.outbox import OutboxMessage
from app.services.payment import create_payment
from app.workers import outbox as outbox_module
from tests.conftest import make_create_payload


async def test_publish_outbox_batch_marks_messages_published(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch,
) -> None:
    payment, _ = await create_payment(session, make_create_payload(), "outbox-pub")
    await session.commit()

    @asynccontextmanager
    async def factory():
        async with session_factory() as db_session:
            yield db_session

    monkeypatch.setattr(outbox_module, "async_session_factory", factory)
    publish = AsyncMock()
    monkeypatch.setattr(outbox_module.broker, "publish", publish)

    count = await outbox_module.publish_outbox_batch()
    assert count == 1
    publish.assert_awaited_once()
    kwargs = publish.await_args.kwargs
    assert kwargs["routing_key"] == "payments.new"

    event = (
        await session.execute(select(OutboxMessage).where(OutboxMessage.aggregate_id == payment.id))
    ).scalar_one()
    await session.refresh(event)
    assert event.published_at is not None


async def test_publish_outbox_keeps_message_on_broker_error(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch,
) -> None:
    await create_payment(session, make_create_payload(), "outbox-fail")
    await session.commit()

    @asynccontextmanager
    async def factory():
        async with session_factory() as db_session:
            yield db_session

    monkeypatch.setattr(outbox_module, "async_session_factory", factory)
    monkeypatch.setattr(
        outbox_module.broker,
        "publish",
        AsyncMock(side_effect=ConnectionError("rabbit down")),
    )

    count = await outbox_module.publish_outbox_batch()
    assert count == 0
    event = (await session.execute(select(OutboxMessage))).scalar_one()
    await session.refresh(event)
    assert event.published_at is None
