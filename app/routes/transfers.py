from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from uuid import UUID
import uuid
import json

from ..database import get_db
from ..models import Account, User, Transaction, TransactionDirection, AccountStatus, Transfer, TransactionCategory, IdempotencyKey
from ..schemas import TransferCreate, TransferOut
from ..security import get_current_user
from ..security import limiter


router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferOut, status_code=201)
@limiter.limit("30/minute")
def create_transfer(
    request: Request,
    transfer: TransferCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a transfer between two accounts.
    Requires Idempotency-Key header for exactly-once semantics.
    """

    # Extract and validate idempotency key
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")

    try:
        # Try to insert idempotency record
        idempotency_record = IdempotencyKey(
            idempotency_key=idempotency_key,
            user_id=current_user.id,
            endpoint="POST /transfers",
            response_code=0,
            response_body=""
        )
        db.add(idempotency_record)
        # Force check for duplicate key (unallowed)
        db.flush()
    

        # Successfully inserted - first request, execute transfer
        # Validate amount
        if transfer.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        # Validate source and destination are different
        if transfer.source_account_id == transfer.destination_account_id:
            raise HTTPException(
                status_code=400,
                detail="Source and destination accounts must be different"
            )

        # Fetch source account with row lock
        source_account = db.execute(select(Account).filter(
            Account.id == transfer.source_account_id
        ).with_for_update()).scalar_one_or_none()

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
        destination_account = db.execute(select(Account).filter(
            Account.id == transfer.destination_account_id
        ).with_for_update()).scalar_one_or_none()

        if not destination_account:
            raise HTTPException(status_code=404, detail="Destination account not found")

        # Check destination account is active
        if destination_account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Destination account is not active"
            )

        # Check sufficient balance
        amount_decimal = Decimal(str(transfer.amount))
        if source_account.balance < amount_decimal:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient funds. Available balance: {source_account.balance}"
            )

        # Generate transfer reference
        transfer_id = uuid.uuid4()
        transfer_ref = f"TRF-{str(transfer_id)[:8]}"

        # Create DEBIT transaction for source account
        debit_transaction = Transaction(
            account_id=source_account.id,
            type=TransactionDirection.DEBIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer to account {destination_account.id}",
            reference=transfer_ref,
            category=TransactionCategory.TRANSFER,
            transfer_id=transfer_id
        )
        db.add(debit_transaction)
        db.flush()

        # Create CREDIT transaction for destination account
        credit_transaction = Transaction(
            account_id=destination_account.id,
            type=TransactionDirection.CREDIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer from account {source_account.id}",
            reference=transfer_ref,
            category=TransactionCategory.TRANSFER,
            transfer_id=transfer_id
        )
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

        # Create response
        transfer_result = TransferOut(
            id=db_transfer.id,
            source_account_id=db_transfer.source_account_id,
            destination_account_id=db_transfer.destination_account_id,
            amount=float(db_transfer.amount),
            description=db_transfer.description,
            created_at=db_transfer.created_at,
            source_transaction_id=db_transfer.source_transaction_id,
            destination_transaction_id=db_transfer.destination_transaction_id
        )

        # Store response in idempotency record
        idempotency_record.response_code = 201
        idempotency_record.response_body = transfer_result.model_dump_json()
        idempotency_record.transfer_id = db_transfer.id

        # Commit everything atomically
        db.commit()
        db.refresh(db_transfer)

        return transfer_result

    # duplicate idempotency key
    except IntegrityError as e:
        db.rollback()

        # Check if this is idempotency key constraint violation
        if "idempotency_key" in str(e).lower():
            # Fetch cached response
            cached = db.execute(
                select(IdempotencyKey).filter(
                    IdempotencyKey.idempotency_key == idempotency_key,
                    IdempotencyKey.user_id == current_user.id
                )
            ).scalar_one_or_none()

            if not cached:
                raise HTTPException(status_code=500, detail="Idempotency key check failed")

            # Original request failed - return same error
            if cached.response_code != 201:
                # Original request failed - return same error
                response_data = json.loads(cached.response_body)
                raise HTTPException(
                    status_code=cached.response_code,
                    detail=response_data.get("detail", "Cached error response")
                )

            # Original request succeeded - return message body
            return TransferOut(**json.loads(cached.response_body))


        # Different integrity error (not idempotency)
        raise HTTPException(status_code=400, detail="Database integrity error")

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transfer failed: {str(e)}")


@router.get("", response_model=List[TransferOut])
@limiter.limit("100/minute")
def get_transfers(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all transfers involving the current user.
    """
    # We join with the Account model to filter by the user_id of the owners
    transfers = db.execute(select(Transfer).join(
        Account,
        (Transfer.source_account_id == Account.id) | (Transfer.destination_account_id == Account.id)
    ).filter(
        Account.user_id == current_user.id
    ).distinct().offset(skip).limit(limit)).scalars().all()

    return transfers

@router.get("/{transfer_id}", response_model=TransferOut)
@limiter.limit("100/minute")
def get_transfer_by_id(
    request: Request,
    transfer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details for a specific transfer.
    """
    transfer = db.execute(select(Transfer).filter(Transfer.id == transfer_id)).scalar_one_or_none()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    # Security check: Ensure the user owns one of the accounts involved
    source_acc = db.execute(select(Account).filter(Account.id == transfer.source_account_id)).scalar_one_or_none()
    dest_acc = db.execute(select(Account).filter(Account.id == transfer.destination_account_id)).scalar_one_or_none()

    if source_acc.user_id != current_user.id and dest_acc.user_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="You do not have permission to view this transfer"
        )

    return transfer