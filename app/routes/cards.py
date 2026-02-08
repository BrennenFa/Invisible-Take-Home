from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import secrets
import hmac
import hashlib
import os

from ..database import get_db
from ..models import Card, Account, User, CardType, CardStatus, AccountStatus
from ..schemas import CardCreate, CardOut, CardCreateResponse
from ..security import get_current_user
from ..security import limiter


router = APIRouter(prefix="/cards", tags=["cards"])

# PIN hashing manager
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

CVV_SECRET = os.getenv("CVV_SECRET")


def generate_card_number():
    """Generate a random 16-digit card number."""
    return "".join([str(secrets.randbelow(10)) for _ in range(16)])


def generate_cvv(card_number: str, expiry_date: datetime) -> str:
    """
    Generate a 3-digit CVV using HMAC-SHA256.
    Based on card number + expiry date + secret key.
    Can be regenerated for validation without storage (PCI DSS compliant).

    Args:
        card_number: 16-digit card number
        expiry_date: Card expiry datetime

    Returns:
        3-digit CVV string
    """
    # Create message from card data
    # expiry --> YYYYMM format
    expiry_str = expiry_date.strftime("%Y%m")

    # base string to hash for cvv
    message = f"{card_number}:{expiry_str}".encode('utf-8')

    # Generate HMAC-SHA256
    signature = hmac.new(
        CVV_SECRET.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()

    # Take first 3 digits from hex to use as cvv
    cvv_int = int(signature[:8], 16) % 1000

    # Format as 3-digit string, including leading zeros if necessary
    return f"{cvv_int:03d}"



def validate_cvv(card_number: str, expiry_date: datetime, provided_cvv: str) -> bool:
    """
    Validate a CVV by regenerating it and comparing.

    Args:
        card_number: 16-digit card number
        expiry_date: Card expiry datetime
        provided_cvv: CVV to validate

    Returns:
        True if CVV is valid, False otherwise
    """
    expected_cvv = generate_cvv(card_number, expiry_date)
    return expected_cvv == provided_cvv


@router.post("", response_model=CardCreateResponse, status_code=201)
@limiter.limit("20/minute")
def create_card(
    request: Request,
    card: CardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new card for an account."""


    # Validate account exists and belongs to user
    account = db.execute(select(Account).filter(
        Account.id == card.account_id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Account not found or you don't have access"
        )

    # Check account is active
    if account.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Cannot create card for inactive account"
        )

    # Validate PIN length
    if len(card.pin) != 4 or not card.pin.isdigit():
        raise HTTPException(
            status_code=400,
            detail="PIN must be exactly 4 digits"
        )

    # Generate unique card number using cryptographically secure random
    max_attempts = 100
    card_number = None
    for _ in range(max_attempts):
        card_number = generate_card_number()
        exists = db.execute(select(Card).filter(Card.card_number == card_number)).scalar_one_or_none()
        if not exists:
            break

    if not card_number:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate unique card number. Please try again."
        )

    pin_hash = pwd_context.hash(card.pin)

    # Set expiry date to 3 years from now
    expiry_date = datetime.now(timezone.utc) + timedelta(days=365 * 3)

    # Generate CVV deterministically (not stored in database - PCI DSS compliant)
    cvv = generate_cvv(card_number, expiry_date)

    # Create card WITHOUT storing CVV
    db_card = Card(
        account_id=account.id,
        card_number=card_number,
        card_holder_name=card.card_holder_name,
        pin_hash=pin_hash,
        card_type=card.card_type,
        expiry_date=expiry_date,
        status=CardStatus.ACTIVE,
        spending_limit=card.spending_limit
    )

    db.add(db_card)
    db.commit()
    db.refresh(db_card)

    # Return response with CVV (only time it's ever returned)
    return CardCreateResponse(
        id=db_card.id,
        account_id=db_card.account_id,
        card_number=db_card.card_number,
        card_holder_name=db_card.card_holder_name,
        # Only returned once
        cvv=cvv,
        expiry_date=db_card.expiry_date,
        card_type=db_card.card_type,
        status=db_card.status,
        spending_limit=db_card.spending_limit,
        created_at=db_card.created_at
    )


@router.get("", response_model=List[CardOut])
@limiter.limit("100/minute")
def get_cards(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all cards for the current user's accounts with masked card numbers."""

    cards = db.execute(select(Card).join(Account).filter(
        Account.user_id == current_user.id
    )).scalars().all()

    return [CardOut.from_card(card) for card in cards]


@router.get("/{card_id}", response_model=CardOut)
@limiter.limit("100/minute")
def get_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details for a specific card with masked card number."""

    card = db.execute(select(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found or you don't have access"
        )

    return CardOut.from_card(card)


@router.patch("/{card_id}/freeze", response_model=CardOut)
@limiter.limit("20/minute")
def freeze_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Freeze a card to prevent transactions."""

    card = db.execute(select(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found or you don't have access"
        )

    if card.status == CardStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Cannot freeze a cancelled card"
        )

    if card.status == CardStatus.FROZEN:
        raise HTTPException(
            status_code=400,
            detail="Card is already frozen"
        )

    card.status = CardStatus.FROZEN
    db.commit()
    db.refresh(card)

    return CardOut.from_card(card)


@router.patch("/{card_id}/unfreeze", response_model=CardOut)
@limiter.limit("20/minute")
def unfreeze_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unfreeze a card to allow transactions."""

    card = db.execute(select(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found or you don't have access"
        )

    if card.status != CardStatus.FROZEN:
        raise HTTPException(
            status_code=400,
            detail="Card is not frozen"
        )

    card.status = CardStatus.ACTIVE
    db.commit()
    db.refresh(card)

    return CardOut.from_card(card)


@router.delete("/{card_id}", response_model=CardOut)
@limiter.limit("20/minute")
def cancel_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a card permanently."""

    card = db.execute(select(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found or you don't have access"
        )

    if card.status == CardStatus.CANCELLED:
        raise HTTPException(
            status_code=400,
            detail="Card is already cancelled"
        )

    card.status = CardStatus.CANCELLED
    db.commit()
    db.refresh(card)

    return CardOut.from_card(card)
