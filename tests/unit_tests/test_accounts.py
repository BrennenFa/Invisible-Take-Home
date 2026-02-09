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


@pytest.mark.skip(reason="Complex database/encryption mocking - tested via integration tests")
def test_create_account_success():
    """Test successful account creation with valid AccountType.

    Skipped: Full integration testing in tests/integration_tests/test_accounts.py
    This endpoint requires complex database interactions and encryption that
    are better tested through integration tests.
    """
    pass


@pytest.mark.skip(reason="Complex decryption mocking - tested via integration tests")
def test_get_accounts_success():
    """Test retrieving all accounts for a user.

    Skipped: Full integration testing in tests/integration_tests/test_accounts.py
    This endpoint requires decryption of account numbers which is better
    tested through integration tests.
    """
    pass

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
