from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from decimal import Decimal
from uuid import UUID
from datetime import datetime
import uuid
import json
import time

from ..database import get_db
from ..models import Account, User, Transaction, TransactionDirection, AccountStatus, Transfer, TransactionCategory, IdempotencyKey
from ..schemas import TransferCreate, TransferOut, TransferCreateByAccountNumber
from ..security import get_current_user, encrypt_account_number
import hashlib
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
        # Try to insert idempotency record first (acts as a lock)
        idempotency_record = IdempotencyKey(
            idempotency_key=idempotency_key,
            user_id=current_user.id,
            endpoint="POST /transfers",
            response_code=0,
            response_body=""
        )
        db.add(idempotency_record)
        
        # flush will raise integrity error if key already exists
        db.flush()

        # Validate amount
        if transfer.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        # Validate source and destination are different
        if transfer.source_account_id == transfer.destination_account_id:
            raise HTTPException(
                status_code=400,
                detail="Source and destination accounts must be different"
            )

        # Lock accounts to prevent deadlock
        account_ids = sorted([transfer.source_account_id, transfer.destination_account_id])
        locked_accounts = {}
        for acc_id in account_ids:
            acc = db.execute(select(Account).filter(
                Account.id == acc_id
            ).with_for_update()).scalar_one_or_none()

            if not acc:
                raise HTTPException(status_code=404, detail="Account not found")

            locked_accounts[acc_id] = acc

        source_account = locked_accounts[transfer.source_account_id]
        destination_account = locked_accounts[transfer.destination_account_id]

        # Verify source account belongs to current user
        if source_account.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to transfer from this account"
            )

        # Check both accounts are active
        if source_account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Source account is not active"
            )

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

        # Pre-generate all UUIDs in memory (no database calls)
        transfer_id = uuid.uuid4()
        debit_txn_id = uuid.uuid4()
        credit_txn_id = uuid.uuid4()
        transfer_ref = f"TRF-{str(transfer_id)[:8]}"
        created_at = datetime.utcnow()

        # Update account balances
        source_account.balance -= amount_decimal
        destination_account.balance += amount_decimal

        # Create all objects in memory (before any more database writes)
        debit_transaction = Transaction(
            id=debit_txn_id,
            account_id=source_account.id,
            type=TransactionDirection.DEBIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer to account {destination_account.id}",
            reference=transfer_ref,
            category=TransactionCategory.TRANSFER,
            transfer_id=transfer_id,
            created_at=created_at
        )

        credit_transaction = Transaction(
            id=credit_txn_id,
            account_id=destination_account.id,
            type=TransactionDirection.CREDIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer from account {source_account.id}",
            reference=transfer_ref,
            category=TransactionCategory.TRANSFER,
            transfer_id=transfer_id,
            created_at=created_at
        )

        db_transfer = Transfer(
            id=transfer_id,
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            amount=amount_decimal,
            description=transfer.description,
            source_transaction_id=debit_txn_id,
            destination_transaction_id=credit_txn_id,
            created_at=created_at
        )

        # Single atomic write
        db.add_all([debit_transaction, credit_transaction, db_transfer])

        # Create response (use our pre-generated timestamp)
        transfer_result = TransferOut(
            id=db_transfer.id,
            source_account_id=db_transfer.source_account_id,
            destination_account_id=db_transfer.destination_account_id,
            amount=float(db_transfer.amount),
            description=db_transfer.description,
            created_at=created_at,
            source_transaction_id=db_transfer.source_transaction_id,
            destination_transaction_id=db_transfer.destination_transaction_id
        )

        # Store response in idempotency record and commit atomically
        idempotency_record.response_code = 201
        idempotency_record.response_body = transfer_result.model_dump_json()
        idempotency_record.transfer_id = db_transfer.id

        db.commit()
        db.refresh(db_transfer)

        return transfer_result

    # duplicate idempotency key
    except IntegrityError as e:
        db.rollback()

        # Check if this is idempotency key constraint violation
        if "idempotency_key" in str(e).lower():
            # Another concurrent request is processing or has completed
            # Wait for it to finish and return its result
            max_wait = 5
            poll_interval = 0.1
            elapsed = 0

            while elapsed < max_wait:
                # Fetch cached response
                cached = db.execute(
                    select(IdempotencyKey).filter(
                        IdempotencyKey.idempotency_key == idempotency_key,
                        IdempotencyKey.user_id == current_user.id
                    )
                ).scalar_one_or_none()

                if not cached:
                    raise HTTPException(status_code=500, detail="Idempotency key check failed")

                # Wait til response is ready
                if cached.response_code == 0:
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    continue

                # First request completed - return its response
                if cached.response_code == 201:
                    return TransferOut(**json.loads(cached.response_body))
                else:
                    # First request failed - return same error
                    response_data = json.loads(cached.response_body)
                    raise HTTPException(
                        status_code=cached.response_code,
                        detail=response_data.get("detail", "Cached error response")
                    )

            # Timeout waiting for first request to complete
            raise HTTPException(status_code=503, detail="Request timeout: concurrent request did not complete in time")

        # Different integrity error (not idempotency)
        raise HTTPException(status_code=400, detail="Database integrity error")


    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transfer failed: {str(e)}")


@router.post("/account", response_model=TransferOut, status_code=201)
@limiter.limit("30/minute")
def create_transfer_by_account_number(
    request: Request,
    transfer: TransferCreateByAccountNumber,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a transfer using recipient's account number and routing number.
    Requires Idempotency-Key header for exactly-once semantics.
    """

    # Extract and validate idempotency key
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")

    try:
        # Try to insert idempotency record first (acts as a lock)
        idempotency_record = IdempotencyKey(
            idempotency_key=idempotency_key,
            user_id=current_user.id,
            endpoint="POST /transfers/account",
            response_code=0,
            response_body=""
        )
        db.add(idempotency_record)
        db.flush()

        # Validate amount
        if transfer.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        # Look up destination account by account number hash and routing number
        account_number_hash = hashlib.sha256(transfer.destination_account_number.encode()).hexdigest()
        destination_account = db.execute(select(Account).filter(
            Account.account_number_hash == account_number_hash,
            Account.routing_number == transfer.destination_routing_number
        ).with_for_update()).scalar_one_or_none()

        if not destination_account:
            raise HTTPException(status_code=404, detail="Recipient account not found")

        # Get source account
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

        # Verify source and destination are different
        if source_account.id == destination_account.id:
            raise HTTPException(
                status_code=400,
                detail="Source and destination accounts must be different"
            )

        # Check both accounts are active
        if source_account.status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Source account is not active"
            )

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

        # Pre-generate all UUIDs in memory
        transfer_id = uuid.uuid4()
        debit_txn_id = uuid.uuid4()
        credit_txn_id = uuid.uuid4()
        transfer_ref = f"TRF-{str(transfer_id)[:8]}"
        created_at = datetime.utcnow()

        # Update account balances
        source_account.balance -= amount_decimal
        destination_account.balance += amount_decimal

        # Create all objects in memory
        debit_transaction = Transaction(
            id=debit_txn_id,
            account_id=source_account.id,
            type=TransactionDirection.DEBIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer to account {destination_account.account_number_masked}",
            reference=transfer_ref,
            category=TransactionCategory.TRANSFER,
            transfer_id=transfer_id,
            created_at=created_at
        )

        credit_transaction = Transaction(
            id=credit_txn_id,
            account_id=destination_account.id,
            type=TransactionDirection.CREDIT,
            amount=amount_decimal,
            description=transfer.description or f"Transfer from account {source_account.account_number_masked}",
            reference=transfer_ref,
            category=TransactionCategory.TRANSFER,
            transfer_id=transfer_id,
            created_at=created_at
        )

        db_transfer = Transfer(
            id=transfer_id,
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            amount=amount_decimal,
            description=transfer.description,
            source_transaction_id=debit_txn_id,
            destination_transaction_id=credit_txn_id,
            created_at=created_at
        )

        # Single atomic write
        db.add_all([debit_transaction, credit_transaction, db_transfer])

        # Create response
        transfer_result = TransferOut(
            id=db_transfer.id,
            source_account_id=db_transfer.source_account_id,
            destination_account_id=db_transfer.destination_account_id,
            amount=float(db_transfer.amount),
            description=db_transfer.description,
            created_at=created_at,
            source_transaction_id=db_transfer.source_transaction_id,
            destination_transaction_id=db_transfer.destination_transaction_id
        )

        # Store response in idempotency record and commit atomically
        idempotency_record.response_code = 201
        idempotency_record.response_body = transfer_result.model_dump_json()
        idempotency_record.transfer_id = db_transfer.id

        db.commit()
        db.refresh(db_transfer)

        return transfer_result

    except IntegrityError as e:
        db.rollback()

        if "idempotency_key" in str(e).lower():
            max_wait = 5
            poll_interval = 0.1
            elapsed = 0

            while elapsed < max_wait:
                cached = db.execute(
                    select(IdempotencyKey).filter(
                        IdempotencyKey.idempotency_key == idempotency_key,
                        IdempotencyKey.user_id == current_user.id
                    )
                ).scalar_one_or_none()

                if not cached:
                    raise HTTPException(status_code=500, detail="Idempotency key check failed")

                if cached.response_code == 0:
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    continue

                if cached.response_code == 201:
                    return TransferOut(**json.loads(cached.response_body))
                else:
                    response_data = json.loads(cached.response_body)
                    raise HTTPException(
                        status_code=cached.response_code,
                        detail=response_data.get("detail", "Cached error response")
                    )

            raise HTTPException(status_code=503, detail="Request timeout: concurrent request did not complete in time")

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