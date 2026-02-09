from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import os

from ..database import get_db
from ..models import Account, User, AccountType, AccountStatus, Transaction
from ..schemas import AccountCreate, AccountOut, TransactionOut, AccountCreateResponse
from ..security import get_current_user, encrypt_account_number, mask_account_number, generate_account_number, decrypt_account_number
import hashlib
from ..security import limiter

# accounts routes
router = APIRouter(prefix="/accounts", tags=["accounts"])

# Create account
@router.post("", response_model=AccountCreateResponse, status_code=201)
@limiter.limit("20/minute")
def create_account(
    request: Request,
    account: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new account for the current user.
    Returns full account number for setup/transfer purposes.
    """

    # Generate unique account number
    routing_number = os.getenv("BANK_ROUTING_NUMBER", "123456789")
    account_number = None

    for _ in range(100):
        account_number = generate_account_number()
        encrypted = encrypt_account_number(account_number)
        if not db.query(Account).filter(Account.account_number_encrypted == encrypted).first():
            break

    if not account_number:
        raise HTTPException(500, "Failed to generate unique account number")

    # Compute hash of account number for lookups
    account_number_hash = hashlib.sha256(account_number.encode()).hexdigest()

    db_account = Account(
        user_id=current_user.id,
        type=account.type,
        balance=0.0,
        status=AccountStatus.ACTIVE,
        routing_number=routing_number,
        account_number_encrypted=encrypt_account_number(account_number),
        account_number_hash=account_number_hash,
        account_number_masked=mask_account_number(account_number)
    )

    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    # Return response with full account number
    return AccountCreateResponse(
        id=db_account.id,
        user_id=db_account.user_id,
        type=db_account.type,
        balance=db_account.balance,
        status=db_account.status,
        created_at=db_account.created_at,
        routing_number=db_account.routing_number,
        account_number_masked=db_account.account_number_masked,
        account_number=account_number
    )

# Get accounts for current user
@router.get("", response_model=List[AccountCreateResponse])
@limiter.limit("100/minute")
def get_accounts(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all accounts for the current user, including full account numbers.
    """
    accounts = db.execute(select(Account).filter(Account.user_id == current_user.id)).scalars().all()

    # Decrypt account numbers for display
    result = []
    for account in accounts:
        full_account_number = decrypt_account_number(account.account_number_encrypted)
        result.append(AccountCreateResponse(
            id=account.id,
            user_id=account.user_id,
            type=account.type,
            balance=account.balance,
            status=account.status,
            created_at=account.created_at,
            routing_number=account.routing_number,
            account_number_masked=account.account_number_masked,
            account_number=full_account_number
        ))

    return result


# Get specific account by ID
@router.get("/{id}", response_model=AccountOut)
@limiter.limit("100/minute")
def get_account(
    request: Request,
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details for a specific account.
    """
    # validate that account belongs to user
    account = db.execute(select(Account).filter(
        Account.id == id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return account


# Get account transations
@router.get("/{id}/transactions", response_model=List[TransactionOut])
@limiter.limit("100/minute")
def get_account_transactions(
    request: Request,
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all transactions for a specific account.
    """
    account = db.execute(select(Account).filter(
        Account.id == id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    transactions = db.execute(select(Transaction).filter(
        Transaction.account_id == id
    ).order_by(Transaction.created_at.desc())).scalars().all()

    return transactions


# Freeze account
@router.patch("/{id}/freeze", response_model=AccountOut)
@limiter.limit("20/minute")
def freeze_account(
    request: Request,
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Freeze an account to prevent transactions."""

    account = db.execute(select(Account).filter(
        Account.id == id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.status == AccountStatus.CLOSED:
        raise HTTPException(
            status_code=400,
            detail="Cannot freeze a closed account"
        )

    if account.status == AccountStatus.FROZEN:
        raise HTTPException(
            status_code=400,
            detail="Account is already frozen"
        )

    account.status = AccountStatus.FROZEN
    db.commit()
    db.refresh(account)

    return account


# Unfreeze account
@router.patch("/{id}/unfreeze", response_model=AccountOut)
@limiter.limit("20/minute")
def unfreeze_account(
    request: Request,
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unfreeze an account to allow transactions."""

    account = db.execute(select(Account).filter(
        Account.id == id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.status != AccountStatus.FROZEN:
        raise HTTPException(
            status_code=400,
            detail="Account is not frozen"
        )

    account.status = AccountStatus.ACTIVE
    db.commit()
    db.refresh(account)

    return account


# Close account
@router.patch("/{id}/close", response_model=AccountOut)
@limiter.limit("20/minute")
def close_account(
    request: Request,
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Close an account permanently. Account must have zero balance."""

    account = db.execute(select(Account).filter(
        Account.id == id,
        Account.user_id == current_user.id
    )).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.status == AccountStatus.CLOSED:
        raise HTTPException(
            status_code=400,
            detail="Account is already closed"
        )

    # Check for zero balance
    if account.balance != 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot close account with non-zero balance. Please withdraw or transfer all funds first."
        )

    account.status = AccountStatus.CLOSED
    db.commit()
    db.refresh(account)

    return account


