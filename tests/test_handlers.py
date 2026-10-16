from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.broker import handlers
from app.broker.handlers import _retry_count, handle_new_payment
from app.broker.topology import MAX_PROCESSING_ATTEMPTS, retry_routing_key
from app.schemas.payment import PaymentNewEvent


class FakeSessionFactory:
    async def __aenter__(self) -> MagicMock:
        return MagicMock()

    async def __aexit__(self, *_args) -> None:
        return None


def _event() -> PaymentNewEvent:
    return PaymentNewEvent(payment_id=uuid4())


def test_retry_count_from_headers() -> None:
    message = MagicMock()
    message.headers = {"x-retry-count": "2"}
    assert _retry_count(message) == 2
    message.headers = {"x-retry-count": "bad"}
    assert _retry_count(message) == 0
    message.headers = None
    assert _retry_count(message) == 0


async def test_successful_processing_acks_message(monkeypatch) -> None:
    monkeypatch.setattr(handlers, "async_session_factory", lambda: FakeSessionFactory())
    monkeypatch.setattr(handlers, "process_payment_event", AsyncMock())
    message = AsyncMock()
    message.headers = {}
    await handle_new_payment(_event(), message, MagicMock())
    message.ack.assert_awaited_once()
    message.reject.assert_not_called()


async def test_failure_schedules_retry_and_acks(monkeypatch) -> None:
    monkeypatch.setattr(handlers, "async_session_factory", lambda: FakeSessionFactory())
    monkeypatch.setattr(
        handlers,
        "process_payment_event",
        AsyncMock(side_effect=RuntimeError("webhook failed")),
    )
    publish = AsyncMock()
    monkeypatch.setattr(handlers.broker, "publish", publish)

    event = _event()
    message = AsyncMock()
    message.headers = {}
    await handle_new_payment(event, message, MagicMock())

    publish.assert_awaited_once()
    kwargs = publish.await_args.kwargs
    assert kwargs["routing_key"] == retry_routing_key(1)
    assert kwargs["headers"]["x-retry-count"] == "1"
    message.ack.assert_awaited_once()
    message.reject.assert_not_called()


async def test_last_attempt_rejects_to_dlq(monkeypatch) -> None:
    monkeypatch.setattr(handlers, "async_session_factory", lambda: FakeSessionFactory())
    monkeypatch.setattr(
        handlers,
        "process_payment_event",
        AsyncMock(side_effect=RuntimeError("still failing")),
    )
    publish = AsyncMock()
    monkeypatch.setattr(handlers.broker, "publish", publish)

    message = AsyncMock()
    message.headers = {"x-retry-count": str(MAX_PROCESSING_ATTEMPTS - 1)}
    await handle_new_payment(_event(), message, MagicMock())

    publish.assert_not_called()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_called()
