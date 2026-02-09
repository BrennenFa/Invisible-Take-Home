import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, Request
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError

# Import the code to be tested
from app.routes.accounts import create_account, get_accounts
from app.models import User, Account, AccountType, AccountStatus
from app.schemas import AccountCreate


# mock request for slow api
def create_mock_request():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [],
    }
    return Request(scope=scope)

mock_request = create_mock_request()


def test_create_account_success():
    """Test successful account creation with valid AccountType."""
    mock_db = MagicMock()
    mock_user = User(id=uuid4(), email="user@test.com")

    account_in = AccountCreate(type=AccountType.CHECKING)

    response = create_account(
        request=mock_request,
        account=account_in,
        current_user=mock_user,
        db=mock_db
    )

    # Verify account was added and committed
    assert mock_db.add.called
    assert mock_db.commit.called


def test_get_accounts_success():
    """Test retrieving all accounts for a user."""
    mock_db = MagicMock()
    mock_user = User(id=uuid4(), email="user@test.com")

    # Simulate two accounts in the database
    fake_accounts = [
        Account(
            id=uuid4(),
            user_id=mock_user.id,
            type=AccountType.CHECKING,
            balance=100.0,
            status=AccountStatus.ACTIVE,
            created_at=datetime.now(timezone.utc)
        ),
        Account(
            id=uuid4(),
            user_id=mock_user.id,
            type=AccountType.SAVINGS,
            balance=500.0,
            status=AccountStatus.ACTIVE,
            created_at=datetime.now(timezone.utc)
        )
    ]

    mock_db.execute().scalars().all.return_value = fake_accounts

    response = get_accounts(
        request=mock_request,
        current_user=mock_user,
        db=mock_db
    )

    assert len(response) == 2
    assert response[0].type == AccountType.CHECKING
    assert response[1].type == AccountType.SAVINGS
    assert response[0].balance == 100.0
    assert response[1].balance == 500.0
    assert response[0].user_id == mock_user.id
    assert response[1].user_id == mock_user.id

# =================================================================
# Validation Tests
# =================================================================

def test_account_type_validation_checking():
    """Test that CHECKING is a valid AccountType."""
    account = AccountCreate(type=AccountType.CHECKING)
    assert account.type == AccountType.CHECKING


def test_account_type_validation_savings():
    """Test that SAVINGS is a valid AccountType."""
    account = AccountCreate(type=AccountType.SAVINGS)
    assert account.type == AccountType.SAVINGS


def test_account_type_validation_string_checking():
    """Test that string 'CHECKING' gets converted to enum."""
    account = AccountCreate(type="CHECKING")
    assert account.type == AccountType.CHECKING


def test_account_type_validation_string_savings():
    """Test that string 'SAVINGS' gets converted to enum."""
    account = AccountCreate(type="SAVINGS")
    assert account.type == AccountType.SAVINGS


def test_account_type_validation_invalid():
    """Test that invalid account type raises ValidationError."""
    with pytest.raises(ValidationError) as exc:
        AccountCreate(type="INVALID_TYPE")

    assert "Input should be" in str(exc.value)
