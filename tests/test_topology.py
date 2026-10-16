from app.broker.topology import (
    DLQ_NAME,
    MAX_PROCESSING_ATTEMPTS,
    NEW_QUEUE_NAME,
    RETRY_TTL_MS,
    new_queue,
    retry_queue,
    retry_routing_key,
)


def test_retry_routing_keys_and_ttl() -> None:
    assert MAX_PROCESSING_ATTEMPTS == 3
    assert RETRY_TTL_MS[1] == 2000
    assert RETRY_TTL_MS[2] == 4000
    assert retry_routing_key(1) == "payments.retry.1"
    queue = retry_queue(1)
    assert queue.durable is True
    assert queue.arguments["x-message-ttl"] == 2000
    assert queue.arguments["x-dead-letter-routing-key"] == "payments.new"


def test_main_queue_has_dlx() -> None:
    assert new_queue.name == NEW_QUEUE_NAME
    assert new_queue.arguments["x-dead-letter-routing-key"] == DLQ_NAME
    assert new_queue.arguments["x-dead-letter-exchange"] == "payments.dlx"
