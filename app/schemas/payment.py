import hashlib
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.models.payment import Currency, PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Currency
    description: str = Field(min_length=1, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: AnyHttpUrl

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PaymentAccepted(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus
    created_at: datetime


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata")
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
    webhook_sent_at: datetime | None


class PaymentNewEvent(BaseModel):
    payment_id: uuid.UUID
    event_type: str = "payments.new"


class WebhookPayload(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any]
    processed_at: datetime | None
