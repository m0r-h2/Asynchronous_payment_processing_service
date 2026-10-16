import asyncio
import logging

from faststream import FastStream

from app.broker import handlers as _handlers  # noqa: F401
from app.broker.rabbit import broker, declare_topology
from app.http_client import close_http_client
from app.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastStream(broker)


@app.on_startup
async def on_startup() -> None:
    await declare_topology()
    logger.info("Payment consumer topology is ready")


@app.after_startup
async def after_startup() -> None:
    logger.info("Payment consumer started")


@app.after_shutdown
async def on_shutdown() -> None:
    await close_http_client()


if __name__ == "__main__":
    asyncio.run(app.run())
