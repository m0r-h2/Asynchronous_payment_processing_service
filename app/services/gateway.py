import asyncio
import random
import uuid

from app.models.payment import PaymentStatus

PROCESSING_DELAY_MIN_SEC = 2.0
PROCESSING_DELAY_MAX_SEC = 5.0
SUCCESS_RATE = 0.9


async def emulate_payment_processing(payment_id: uuid.UUID) -> PaymentStatus:
    """Emulates an external payment gateway: 2-5s delay, 90% success."""
    delay = random.uniform(PROCESSING_DELAY_MIN_SEC, PROCESSING_DELAY_MAX_SEC)
    await asyncio.sleep(delay)
    if random.random() < SUCCESS_RATE:
        return PaymentStatus.SUCCEEDED
    return PaymentStatus.FAILED
