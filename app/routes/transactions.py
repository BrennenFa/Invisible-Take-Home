from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from ..database import get_db
from ..models import Account, User, Transaction, TransactionDirection, AccountStatus, TransactionCategory, Card, CardStatus
from ..schemas import DepositCreate, WithdrawalCreate, TransactionOut, CardPaymentCreate
from ..security import get_current_user
from ..rate_limit import limiter
from datetime import datetime


router = APIRouter(prefix="/transactions", tags=["transactions"], dependencies=[Depends(limiter.limit("100/minute"))])


@router.post("/deposit", response_model=TransactionOut, status_code=201)
def create_deposit(
    deposit: DepositCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a deposit transaction for an account."""

    # Validate amount is positive
    if deposit.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    try:
        # Fetch account with row lock
        account = db.query(Account).filter(
            Account.id == deposit.account_id
        ).with_for_update().first()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify account belongs to current user
        if account.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to deposit to this account"
            )

        # Check account is active
        if account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Account is not active"
            )

        # Convert amount to Decimal
        amount_decimal = Decimal(str(deposit.amount))

        # Create CREDIT transaction (deposit adds money)
        transaction = Transaction(
            account_id=account.id,
            type=TransactionDirection.CREDIT,
            amount=amount_decimal,
            description=deposit.description or "Deposit",
            reference=None,
            category=TransactionCategory.DEPOSIT
        )

        db.add(transaction)
        db.flush()

        # Update account balance
        account.balance += amount_decimal

        db.commit()
        db.refresh(transaction)

        return transaction

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Deposit failed: {str(e)}")


@router.post("/withdrawal", response_model=TransactionOut, status_code=201)
def create_withdrawal(
    withdrawal: WithdrawalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a withdrawal transaction for an account."""

    # Validate amount is positive
    if withdrawal.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    try:
        # Fetch account with row lock
        account = db.query(Account).filter(
            Account.id == withdrawal.account_id
        ).with_for_update().first()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Verify account belongs to current user
        if account.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to withdraw from this account"
            )

        # Check account is active
        if account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Account is not active"
            )

        # Convert amount to Decimal
        amount_decimal = Decimal(str(withdrawal.amount))

        # Check sufficient balance (including overdraft)
        available_balance = account.balance + account.overdraft_limit
        if available_balance < amount_decimal:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient funds. Available (including overdraft): {available_balance}"
            )

        # Create DEBIT transaction (withdrawal removes money)
        transaction = Transaction(
            account_id=account.id,
            type=TransactionDirection.DEBIT,
            amount=amount_decimal,
            description=withdrawal.description or "Withdrawal",
            reference=None,
            category=TransactionCategory.WITHDRAWAL
        )

        db.add(transaction)
        db.flush()

        # Update account balance
        account.balance -= amount_decimal

        db.commit()
        db.refresh(transaction)

        return transaction

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Withdrawal failed: {str(e)}")






@router.post("/card-payment", response_model=TransactionOut, status_code=201)
def create_card_payment(
    payment: CardPaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a card payment transaction."""

    # Validate amount is positive
    if payment.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    try:
        # Fetch card with account
        card = db.query(Card).join(Account).filter(
            Card.id == payment.card_id,
            Account.user_id == current_user.id
        ).first()

        if not card:
            raise HTTPException(
                status_code=404,
                detail="Card not found or you don't have access"
            )

        # Check card status
        if card.status == CardStatus.FROZEN:
            raise HTTPException(
                status_code=400,
                detail="Card is frozen. Please unfreeze to make payments."
            )

        if card.status == CardStatus.CANCELLED:
            raise HTTPException(
                status_code=400,
                detail="Card is cancelled and cannot be used."
            )

        # Check card expiry
        if card.expiry_date < datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="Card has expired"
            )

        # Check spending limit
        if card.spending_limit:
            amount_decimal = Decimal(str(payment.amount))
            if amount_decimal > card.spending_limit:
                raise HTTPException(
                    status_code=400,
                    detail=f"Payment exceeds card spending limit of {card.spending_limit}"
                )

        # Fetch account with row lock
        account = db.query(Account).filter(
            Account.id == card.account_id
        ).with_for_update().first()

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Check account is active
        if account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Account is not active"
            )

        # Convert amount to Decimal
        amount_decimal = Decimal(str(payment.amount))

        # Check sufficient balance (including overdraft)
        available_balance = account.balance + account.overdraft_limit
        if available_balance < amount_decimal:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient funds. Available (including overdraft): {available_balance}"
            )

        # Create DEBIT transaction (card payment removes money)
        transaction = Transaction(
            account_id=account.id,
            type=TransactionDirection.DEBIT,
            amount=amount_decimal,
            description=payment.description or f"Card payment - {payment.merchant or 'Merchant'}",
            reference=None,
            category=TransactionCategory.CARD_PAYMENT,
            card_id=card.id
        )

        db.add(transaction)
        db.flush()

        # Update account balance
        account.balance -= amount_decimal

        db.commit()
        db.refresh(transaction)

        return transaction

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Card payment failed: {str(e)}")


@router.get("", response_model=List[TransactionOut])
def get_transactions(
    account_id: Optional[UUID] = Query(None, description="Filter by account ID"),
    category: Optional[str] = Query(None, description="Filter by category (TRANSFER, DEPOSIT, WITHDRAWAL, CARD_PAYMENT)"),
    start_date: Optional[datetime] = Query(None, description="Filter transactions from this date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter transactions until this date (ISO format)"),
    limit: int = Query(50, ge=1, le=100, description="Number of transactions to return"),
    offset: int = Query(0, ge=0, description="Number of transactions to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get transactions for the current user. Can filter by account_id, category, and date range."""

    # Start with base query - only transactions from user's accounts
    query = db.query(Transaction).join(Account).filter(
        Account.user_id == current_user.id
    )

    # Apply filters
    if account_id:
        # Verify account belongs to user
        account = db.query(Account).filter(
            Account.id == account_id,
            Account.user_id == current_user.id
        ).first()

        if not account:
            raise HTTPException(
                status_code=404,
                detail="Account not found or you don't have access"
            )

        query = query.filter(Transaction.account_id == account_id)

    if category:
        try:
            category_enum = TransactionCategory[category.upper()]
            query = query.filter(Transaction.category == category_enum)
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join([c.value for c in TransactionCategory])}"
            )

    # Date range filtering
    if start_date:
        query = query.filter(Transaction.created_at >= start_date)

    if end_date:
        query = query.filter(Transaction.created_at <= end_date)

    # Order by most recent first
    query = query.order_by(Transaction.created_at.desc())

    # Apply pagination
    transactions = query.offset(offset).limit(limit).all()

    return transactions
