import asyncio
import logging

import httpx

from app.config import settings
from app.schemas.payment import WebhookPayload

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


async def send_webhook(client: httpx.AsyncClient, url: str, payload: WebhookPayload) -> None:
    last_error: Exception | None = None
    body = payload.model_dump(mode="json")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.post(
                url,
                json=body,
                timeout=settings.webhook_timeout_sec,
            )
            response.raise_for_status()
            logger.info("Webhook delivered to %s (attempt %s)", url, attempt)
            return
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Webhook attempt %s/%s to %s failed: %s",
                attempt,
                MAX_ATTEMPTS,
                url,
                exc,
            )
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(2 ** (attempt - 1))

    assert last_error is not None
    raise last_error
