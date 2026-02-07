from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime, timedelta
from passlib.context import CryptContext
import random

from ..database import get_db
from ..models import Card, Account, User, CardType, CardStatus, AccountStatus
from ..schemas import CardCreate, CardOut
from ..security import get_current_user
from ..security import limiter


router = APIRouter(prefix="/cards", tags=["cards"])

# PIN hashing manager
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_card_number():
    """Generate a random 16-digit card number."""
    return "".join([str(random.randint(0, 9)) for _ in range(16)])


def generate_cvv():
    """Generate a random 3-digit CVV."""
    return "".join([str(random.randint(0, 9)) for _ in range(3)])


@router.post("", response_model=CardOut, status_code=201)
@limiter.limit("20/minute")
def create_card(
    request: Request,
    card: CardCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new card for an account."""

    # Validate card type
    try:
        card_type = CardType[card.card_type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid card type. Must be one of: {', '.join([t.name for t in CardType])}"
        )

    # Validate account exists and belongs to user
    account = db.query(Account).filter(
        Account.id == card.account_id,
        Account.user_id == current_user.id
    ).first()

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

    # Generate unique card number
    max_attempts = 100
    card_number = None
    for _ in range(max_attempts):
        card_number = generate_card_number()
        exists = db.query(Card).filter(Card.card_number == card_number).first()
        if not exists:
            break

    if not card_number:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate unique card number. Please try again."
        )

    cvv = generate_cvv()
    pin_hash = pwd_context.hash(card.pin)

    # Set expiry date to 3 years from now
    expiry_date = datetime.now(datetime.UTC) + timedelta(days=365 * 3)

    # Create card
    db_card = Card(
        account_id=account.id,
        card_number=card_number,
        card_holder_name=card.card_holder_name,
        cvv=cvv,
        pin_hash=pin_hash,
        card_type=card_type,
        expiry_date=expiry_date,
        status=CardStatus.ACTIVE,
        spending_limit=card.spending_limit
    )

    db.add(db_card)
    db.commit()
    db.refresh(db_card)

    return db_card


@router.get("", response_model=List[CardOut])
@limiter.limit("100/minute")
def get_cards(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all cards for the current user's accounts."""

    cards = db.query(Card).join(Account).filter(
        Account.user_id == current_user.id
    ).all()

    return cards


@router.get("/{card_id}", response_model=CardOut)
@limiter.limit("100/minute")
def get_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details for a specific card."""

    card = db.query(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    ).first()

    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found or you don't have access"
        )

    return card


@router.patch("/{card_id}/freeze", response_model=CardOut)
@limiter.limit("20/minute")
def freeze_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Freeze a card to prevent transactions."""

    card = db.query(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    ).first()

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

    return card


@router.patch("/{card_id}/unfreeze", response_model=CardOut)
@limiter.limit("20/minute")
def unfreeze_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unfreeze a card to allow transactions."""

    card = db.query(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    ).first()

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

    return card


@router.delete("/{card_id}", response_model=CardOut)
@limiter.limit("20/minute")
def cancel_card(
    request: Request,
    card_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a card permanently."""

    card = db.query(Card).join(Account).filter(
        Card.id == card_id,
        Account.user_id == current_user.id
    ).first()

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

    return card
