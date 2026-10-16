import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.db import get_session
from app.schemas.payment import PaymentAccepted, PaymentCreate, PaymentRead
from app.services.payment import IdempotencyConflictError, create_payment, get_payment

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(require_api_key)])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted)
@router.post("/", status_code=status.HTTP_202_ACCEPTED, response_model=PaymentAccepted, include_in_schema=False)
async def create_payment_endpoint(
    payload: PaymentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ],
) -> PaymentAccepted:
    try:
        payment, _created = await create_payment(session, payload, idempotency_key)
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PaymentAccepted(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentRead)
async def get_payment_endpoint(
    payment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentRead:
    payment = await get_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentRead.model_validate(payment)
