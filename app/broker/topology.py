from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

PAYMENTS_EXCHANGE_NAME = "payments"
RETRY_EXCHANGE_NAME = "payments.retry"
DLX_NAME = "payments.dlx"

NEW_QUEUE_NAME = "payments.new"
DLQ_NAME = "payments.new.dlq"
NEW_ROUTING_KEY = "payments.new"

MAX_PROCESSING_ATTEMPTS = 3
RETRY_TTL_MS = {1: 2000, 2: 4000}

payments_exchange = RabbitExchange(
    PAYMENTS_EXCHANGE_NAME,
    type=ExchangeType.DIRECT,
    durable=True,
)
retry_exchange = RabbitExchange(
    RETRY_EXCHANGE_NAME,
    type=ExchangeType.DIRECT,
    durable=True,
)
dlx_exchange = RabbitExchange(
    DLX_NAME,
    type=ExchangeType.DIRECT,
    durable=True,
)

new_queue = RabbitQueue(
    NEW_QUEUE_NAME,
    durable=True,
    routing_key=NEW_ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": DLX_NAME,
        "x-dead-letter-routing-key": DLQ_NAME,
    },
)

dlq = RabbitQueue(
    DLQ_NAME,
    durable=True,
    routing_key=DLQ_NAME,
)


def retry_routing_key(attempt: int) -> str:
    return f"payments.retry.{attempt}"


def retry_queue(attempt: int) -> RabbitQueue:
    return RabbitQueue(
        f"payments.retry.{attempt}",
        durable=True,
        routing_key=retry_routing_key(attempt),
        arguments={
            "x-message-ttl": RETRY_TTL_MS[attempt],
            "x-dead-letter-exchange": PAYMENTS_EXCHANGE_NAME,
            "x-dead-letter-routing-key": NEW_ROUTING_KEY,
        },
    )
