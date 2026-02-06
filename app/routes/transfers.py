from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
import uuid

from ..database import get_db
from ..models import Account, User, Transaction, TransactionType, AccountStatus, Transfer
from ..schemas import TransferCreate, TransferOut
from ..security import get_current_user


router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferOut, status_code=201)
def create_transfer(
    transfer: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # validate that amount is positive
    if transfer.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    # Validate source and destination are different
    if transfer.source_account_id == transfer.destination_account_id:
        raise HTTPException(
            status_code=400,
            detail="Source and destination accounts must be different"
        )

    # database transaction for atomicity
    try:
        # Fetch source account with row lock (concurrency) 
        source_account = db.query(Account).filter(
            Account.id == transfer.source_account_id
        ).with_for_update().first()

        if not source_account:
            raise HTTPException(status_code=404, detail="Source account not found")

        # Verify source account belongs to current user
        if source_account.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to transfer from this account"
            )

        # Check source account is active
        if source_account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Source account is not active"
            )

        # Fetch destination account with row lock
        destination_account = db.query(Account).filter(
            Account.id == transfer.destination_account_id
        ).with_for_update().first()

        if not destination_account:
            raise HTTPException(status_code=404, detail="Destination account not found")

        # Check destination account is active
        if destination_account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Destination account is not active"
            )


        # TODO -- currency swap
        # Check currency match
        if source_account.currency != destination_account.currency:
            raise HTTPException(
                status_code=400,
                detail="Currency mismatch between accounts"
            )

        # Check sufficient balance
        amount_decimal = Decimal(str(transfer.amount))
        if source_account.balance < amount_decimal:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Available: {source_account.balance}"
            )

        # Generate transfer reference
        transfer_id = str(uuid.uuid4())
        transfer_ref = f"TRF-{transfer_id[:8]}"

        # Create DEBIT transaction for source account
        debit_transaction = Transaction(
            account_id=source_account.id,
            type=TransactionType.DEBIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer to account {destination_account.id}",
            reference=transfer_ref
        )

        # add debit transaction to session
        db.add(debit_transaction)
        db.flush()

        # Create CREDIT transaction for destination account
        credit_transaction = Transaction(
            account_id=destination_account.id,
            type=TransactionType.CREDIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer from account {source_account.id}",
            reference=transfer_ref
        )
        # add credit transaction to session
        db.add(credit_transaction)
        db.flush()

        # Update account balances atomically
        source_account.balance -= amount_decimal
        destination_account.balance += amount_decimal

        # Create transfer record
        db_transfer = Transfer(
            id=transfer_id,
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            amount=amount_decimal,
            description=transfer.description,
            source_transaction_id=debit_transaction.id,
            destination_transaction_id=credit_transaction.id
        )
        db.add(db_transfer)

        # Commit all changes
        db.commit()
        db.refresh(db_transfer)

        return TransferOut(
            id=db_transfer.id,
            source_account_id=db_transfer.source_account_id,
            destination_account_id=db_transfer.destination_account_id,
            amount=float(db_transfer.amount),
            description=db_transfer.description,
            created_at=db_transfer.created_at,
            source_transaction_id=db_transfer.source_transaction_id,
            destination_transaction_id=db_transfer.destination_transaction_id
        )

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Database integrity error")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transfer failed: {str(e)}")
