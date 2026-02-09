"""
Unit tests for idempotency key model and unique constraint enforcement.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError
import uuid

from app.models import Base, IdempotencyKey, User
from app.models import RoleType


@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        role=RoleType.USER
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


def test_idempotency_key_creation(test_db, test_user):
    """Test that idempotency key records can be created."""
    key = IdempotencyKey(
        idempotency_key="test-key-123",
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{"id": "abc123"}'
    )
    test_db.add(key)
    test_db.commit()
    test_db.refresh(key)

    assert key.idempotency_key == "test-key-123"
    assert key.user_id == test_user.id
    assert key.response_code == 201
    assert key.response_body == '{"id": "abc123"}'
    assert key.transfer_id is None
    assert key.created_at is not None


def test_idempotency_key_unique_constraint(test_db, test_user):
    """Test that duplicate idempotency keys are rejected."""
    # Insert first key
    key1 = IdempotencyKey(
        idempotency_key="test-key-123",
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{}'
    )
    test_db.add(key1)
    test_db.commit()

    # Try to insert duplicate
    key2 = IdempotencyKey(
        idempotency_key="test-key-123",  # Same key
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{}'
    )
    test_db.add(key2)

    with pytest.raises(IntegrityError):
        test_db.commit()


def test_different_users_same_idempotency_key(test_db):
    """
    Test that different users can have the same idempotency key
    (key is globally unique, not per-user).
    """
    # Create two users
    user1 = User(
        email="user1@example.com",
        hashed_password="hashed_password",
        role=RoleType.USER
    )
    user2 = User(
        email="user2@example.com",
        hashed_password="hashed_password",
        role=RoleType.USER
    )
    test_db.add(user1)
    test_db.add(user2)
    test_db.commit()

    # Try to insert same idempotency key for both users
    key1 = IdempotencyKey(
        idempotency_key="same-key",
        user_id=user1.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{}'
    )
    test_db.add(key1)
    test_db.commit()

    # Second user tries to use same key - should fail
    key2 = IdempotencyKey(
        idempotency_key="same-key",  # Same key
        user_id=user2.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{}'
    )
    test_db.add(key2)

    with pytest.raises(IntegrityError):
        test_db.commit()


def test_idempotency_key_with_transfer_reference(test_db, test_user):
    """Test storing transfer_id reference in idempotency key."""
    from app.models import Account, Transfer, Transaction, AccountType, TransactionDirection
    from decimal import Decimal

    # Create accounts and transfer
    source = Account(user_id=test_user.id, type=AccountType.CHECKING, balance=Decimal("100.00"))
    dest = Account(user_id=test_user.id, type=AccountType.SAVINGS, balance=Decimal("0.00"))
    test_db.add(source)
    test_db.add(dest)
    test_db.flush()

    # Create transactions
    debit_txn = Transaction(
        account_id=source.id,
        type=TransactionDirection.DEBIT,
        amount=Decimal("50.00"),
        description="Test"
    )
    credit_txn = Transaction(
        account_id=dest.id,
        type=TransactionDirection.CREDIT,
        amount=Decimal("50.00"),
        description="Test"
    )
    test_db.add(debit_txn)
    test_db.add(credit_txn)
    test_db.flush()

    # Create transfer
    transfer = Transfer(
        source_account_id=source.id,
        destination_account_id=dest.id,
        amount=Decimal("50.00"),
        source_transaction_id=debit_txn.id,
        destination_transaction_id=credit_txn.id
    )
    test_db.add(transfer)
    test_db.commit()

    # Create idempotency key with transfer reference
    key = IdempotencyKey(
        idempotency_key="test-key",
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{"id": "transfer-123"}',
        transfer_id=transfer.id
    )
    test_db.add(key)
    test_db.commit()
    test_db.refresh(key)

    assert key.transfer_id == transfer.id


def test_idempotency_key_stores_error_response(test_db, test_user):
    """Test storing error responses in idempotency key."""
    key = IdempotencyKey(
        idempotency_key="failed-transfer",
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=400,
        response_body='{"detail": "Insufficient funds"}',
        transfer_id=None
    )
    test_db.add(key)
    test_db.commit()
    test_db.refresh(key)

    assert key.response_code == 400
    assert "Insufficient funds" in key.response_body
    assert key.transfer_id is None


def test_idempotency_key_retrieval(test_db, test_user):
    """Test retrieving idempotency key by key string."""
    from sqlalchemy import select

    key = IdempotencyKey(
        idempotency_key="lookup-key",
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{}'
    )
    test_db.add(key)
    test_db.commit()

    # Retrieve by key
    retrieved = test_db.execute(
        select(IdempotencyKey).filter(
            IdempotencyKey.idempotency_key == "lookup-key",
            IdempotencyKey.user_id == test_user.id
        )
    ).scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.idempotency_key == "lookup-key"
    assert retrieved.response_code == 201


def test_idempotency_key_not_found(test_db, test_user):
    """Test that non-existent idempotency key returns None."""
    from sqlalchemy import select

    retrieved = test_db.execute(
        select(IdempotencyKey).filter(
            IdempotencyKey.idempotency_key == "non-existent",
            IdempotencyKey.user_id == test_user.id
        )
    ).scalar_one_or_none()

    assert retrieved is None


def test_idempotency_key_multiple_endpoints(test_db, test_user):
    """Test storing idempotency keys for different endpoints."""
    key1 = IdempotencyKey(
        idempotency_key="op-123",
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{}'
    )
    key2 = IdempotencyKey(
        idempotency_key="op-123",  # Same key
        user_id=test_user.id,
        endpoint="POST /deposits",  # Different endpoint
        response_code=201,
        response_body='{}'
    )

    test_db.add(key1)
    test_db.commit()

    # Second key with same key but different endpoint should still fail
    # because key is globally unique
    test_db.add(key2)
    with pytest.raises(IntegrityError):
        test_db.commit()


def test_idempotency_key_timestamp(test_db, test_user):
    """Test that created_at timestamp is set automatically."""
    from datetime import datetime

    key = IdempotencyKey(
        idempotency_key="timestamp-test",
        user_id=test_user.id,
        endpoint="POST /transfers",
        response_code=201,
        response_body='{}'
    )
    test_db.add(key)
    test_db.commit()
    test_db.refresh(key)

    assert key.created_at is not None
    assert isinstance(key.created_at, datetime)
