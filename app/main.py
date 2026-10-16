import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI

from app.api.v1 import api_router
from app.broker.rabbit import broker, declare_topology
from app.logging import setup_logging
from app.workers.outbox import run_outbox_publisher

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await declare_topology()
    await broker.start()
    publisher_task = asyncio.create_task(run_outbox_publisher())
    try:
        yield
    finally:
        publisher_task.cancel()
        with suppress(asyncio.CancelledError):
            await publisher_task
        await broker.close()


app = FastAPI(
    title="Asynchronous Payment Processing Service",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook-sink")
async def webhook_sink(payload: dict[str, Any]) -> dict[str, str]:
    logger.info("Webhook received: %s", payload)
    return {"status": "received"}
