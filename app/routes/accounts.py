from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ..database import get_db
from ..models import Account, User, AccountType, AccountStatus, Transaction
from ..schemas import AccountCreate, AccountOut, TransactionOut
from ..security import get_current_user

# accounts routes
router = APIRouter(prefix="/accounts", tags=["accounts"])

# Create account
@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    account: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new account for the current user.
    """
    try:
        account_type = AccountType[account.type.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid account type. Must be one of: {', '.join([t.name for t in AccountType])}"
        )

    db_account = Account(
        user_id=current_user.id,
        type=account_type,
        balance=0.0,
        status=AccountStatus.ACTIVE
    )

    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    return db_account

# Get accounts for current user
@router.get("", response_model=List[AccountOut])
def get_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all accounts for the current user.
    """
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    return accounts


# Get specific account by ID
@router.get("/{id}", response_model=AccountOut)
def get_account(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details for a specific account.
    """
    # validate that account belongs to user
    account = db.query(Account).filter(
        Account.id == id,
        Account.user_id == current_user.id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return account


# Get account transations
@router.get("/{id}/transactions", response_model=List[TransactionOut])
def get_account_transactions(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all transactions for a specific account.
    """
    account = db.query(Account).filter(
        Account.id == id,
        Account.user_id == current_user.id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    transactions = db.query(Transaction).filter(
        Transaction.account_id == id
    ).order_by(Transaction.created_at.desc()).all()

    return transactions
