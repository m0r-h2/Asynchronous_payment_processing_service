from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.payment import Currency
from app.schemas.payment import PaymentCreate


def test_fingerprint_is_stable_for_same_payload() -> None:
    first = PaymentCreate(
        amount=Decimal("10.50"),
        currency=Currency.EUR,
        description="Invoice",
        metadata={"a": 1},
        webhook_url="http://example.com/hook",
    )
    second = PaymentCreate(
        amount=Decimal("10.50"),
        currency=Currency.EUR,
        description="Invoice",
        metadata={"a": 1},
        webhook_url="http://example.com/hook",
    )
    assert first.fingerprint() == second.fingerprint()
    assert len(first.fingerprint()) == 64


def test_fingerprint_changes_when_amount_changes() -> None:
    base = PaymentCreate(
        amount=Decimal("10.00"),
        currency=Currency.RUB,
        description="Same",
        webhook_url="http://example.com/hook",
    )
    other = PaymentCreate(
        amount=Decimal("10.01"),
        currency=Currency.RUB,
        description="Same",
        webhook_url="http://example.com/hook",
    )
    assert base.fingerprint() != other.fingerprint()


@pytest.mark.parametrize(
    "payload",
    [
        {"amount": "0", "currency": "RUB", "description": "x", "webhook_url": "http://ex.com"},
        {"amount": "-1", "currency": "RUB", "description": "x", "webhook_url": "http://ex.com"},
        {"amount": "10.001", "currency": "RUB", "description": "x", "webhook_url": "http://ex.com"},
        {"amount": "10.00", "currency": "GBP", "description": "x", "webhook_url": "http://ex.com"},
        {"amount": "10.00", "currency": "RUB", "description": "", "webhook_url": "http://ex.com"},
        {"amount": "10.00", "currency": "RUB", "description": "x", "webhook_url": "not-a-url"},
    ],
)
def test_invalid_create_payload(payload: dict) -> None:
    with pytest.raises(ValidationError):
        PaymentCreate.model_validate(payload)
