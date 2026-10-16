from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.api.v1 import api_router
from app.db import get_session
from app.models import Base
from app.models.payment import Currency
from app.schemas.payment import PaymentCreate


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **_kw) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, compiler, **_kw) -> str:
    return "CHAR(36)"


@compiles(ENUM, "sqlite")
def _compile_enum_sqlite(_type, compiler, **_kw) -> str:
    return "VARCHAR"


@pytest.fixture
def payment_payload() -> dict:
    return {
        "amount": "199.90",
        "currency": "RUB",
        "description": "Order 1001",
        "metadata": {"order_id": "1001"},
        "webhook_url": "http://example.com/webhook",
    }


@pytest.fixture
def payment_create(payment_payload: dict) -> PaymentCreate:
    return PaymentCreate.model_validate(payment_payload)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as db_session:
        yield db_session


@pytest.fixture
def test_app(session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    application = FastAPI()
    application.include_router(api_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/webhook-sink")
    async def webhook_sink() -> dict[str, str]:
        return {"status": "received"}

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db_session:
            yield db_session

    application.dependency_overrides[get_session] = override_session
    return application


@pytest.fixture
async def client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


def auth_headers(idempotency_key: str = "order-1001") -> dict[str, str]:
    return {
        "X-API-Key": "dev-api-key",
        "Idempotency-Key": idempotency_key,
    }


def make_create_payload(
    *,
    amount: str = "10.00",
    currency: Currency = Currency.USD,
    description: str = "Test payment",
) -> PaymentCreate:
    return PaymentCreate(
        amount=Decimal(amount),
        currency=currency,
        description=description,
        metadata={"source": "test"},
        webhook_url="http://example.com/hook",
    )
