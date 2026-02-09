import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, Request
from uuid import uuid4
from datetime import datetime, timezone

# Import the code to be tested
from app.routes.auth import signup, login
from app.models import User
from app.schemas import UserCreate
from pydantic import ValidationError

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


@patch("app.routes.auth.create_access_token")
def test_signup_success(mock_create_token):
    """Test successful signup logic with a mocked DB."""

    # mock setup
    mock_db = MagicMock()
    mock_create_token.return_value = "fake-jwt-token"
    
    # test user does NOT exist
    mock_db.execute().scalar_one_or_none.return_value = None
    
    user_in = UserCreate(email="new@example.com", password="Password123")

    # initiate signup
    response = signup(request=mock_request, user=user_in, db=mock_db)

    # assert successful response and token creation
    assert response["access_token"] == "fake-jwt-token"
    assert mock_db.add.called
    assert mock_db.commit.called


def test_signup_email_exists():
    """Test that signup raises 400 if email is already in DB."""
    mock_db = MagicMock()
    
    # simulate user already exists in DB
    mock_db.execute().scalar_one_or_none.return_value = User(email="exists@test.com")
    
    user_in = UserCreate(email="exists@test.com", password="Password123")

    with pytest.raises(HTTPException) as exc:
        signup(request=mock_request, user=user_in, db=mock_db)
    
    assert exc.value.status_code == 400
    assert exc.value.detail == "Email already registered"


@patch("app.routes.auth.verify_password")
@patch("app.routes.auth.create_access_token")
def test_login_success(mock_create_token, mock_verify_pw):
    """Test successful login when credentials match."""
    mock_db = MagicMock()

    # assume password works
    mock_verify_pw.return_value = True
    mock_create_token.return_value = "login-token"
    
    # Create mock db with a user that matches the login email
    fake_user = User(
        id=uuid4(), 
        email="user@test.com", 
        hashed_password="hashed_stuff",
        created_at=datetime.now(timezone.utc)
    )
    mock_db.execute().scalar_one_or_none.return_value = fake_user
    
    user_in = UserCreate(email="user@test.com", password="CorrectPassword1")

    response = login(request=mock_request, user=user_in, db=mock_db)
    
    # validate token return
    assert response["access_token"] == "login-token"
    mock_verify_pw.assert_called_once_with("CorrectPassword1", "hashed_stuff")


def test_login_invalid_credentials():
    """Test login fails for missing user."""
    mock_db = MagicMock()
    
    # Simulate: User not found
    mock_db.execute().scalar_one_or_none.return_value = None
    
    user_in = UserCreate(email="wrong@test.com", password="Password123")

    with pytest.raises(HTTPException) as exc:
        login(request=mock_request, user=user_in, db=mock_db)
    
    assert exc.value.status_code == 401


@patch("app.routes.auth.verify_password")
def test_login_wrong_password(mock_verify_pw):
    """Test login fails when user exists but password is incorrect."""
    mock_db = MagicMock()
    
    # User found in the database
    fake_user = User(id=uuid4(), email="user@test.com", hashed_password="correct_hash")
    mock_db.execute().scalar_one_or_none.return_value = fake_user
    
    # The password verification returns false
    mock_verify_pw.return_value = False
    
    user_in = UserCreate(email="user@test.com", password="WrongPassword1")

    # Calling login with wrong password should raise a 401 Unauthorized
    with pytest.raises(HTTPException) as exc:
        login(request=mock_request, user=user_in, db=mock_db)
    
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid credentials"


# =================================================================
# Data Validation Tests
# =================================================================

def test_password_validation_too_short():
    """Test that password must be at least 8 characters."""

    with pytest.raises(ValidationError) as exc:
        UserCreate(email="test@example.com", password="Short1")

    assert "at least 8 characters" in str(exc.value)


def test_password_validation_no_uppercase():
    """Test that password must contain uppercase letter."""

    with pytest.raises(ValidationError) as exc:
        UserCreate(email="test@example.com", password="lowercase123")

    assert "uppercase letter" in str(exc.value)


def test_password_validation_no_lowercase():
    """Test that password must contain lowercase letter."""

    with pytest.raises(ValidationError) as exc:
        UserCreate(email="test@example.com", password="UPPERCASE123")

    assert "lowercase letter" in str(exc.value)


def test_password_validation_no_digit():
    """Test that password must contain a digit."""

    with pytest.raises(ValidationError) as exc:
        UserCreate(email="test@example.com", password="NoDigitsHere")

    assert "digit" in str(exc.value)


def test_password_validation_success():
    """Test that valid password passes validation."""
    user = UserCreate(email="test@example.com", password="ValidPass123")
    assert user.email == "test@example.com"
    assert user.password == "ValidPass123"


# =================================================================
# Password Change Schema Tests
# =================================================================

def test_password_change_validation_success():
    """Test that valid password change passes validation."""
    from app.schemas import PasswordChange
    pwd_change = PasswordChange(
        current_password="OldPass123",
        new_password="NewPass456"
    )
    assert pwd_change.current_password == "OldPass123"
    assert pwd_change.new_password == "NewPass456"


def test_password_change_new_password_too_short():
    """Test that new password must be at least 8 characters."""
    from app.schemas import PasswordChange
    with pytest.raises(ValidationError) as exc:
        PasswordChange(current_password="OldPass123", new_password="Short1")
    assert "at least 8 characters" in str(exc.value)


def test_password_change_new_password_no_uppercase():
    """Test that new password must contain uppercase."""
    from app.schemas import PasswordChange
    with pytest.raises(ValidationError) as exc:
        PasswordChange(current_password="OldPass123", new_password="lowercase123")
    assert "uppercase letter" in str(exc.value)


def test_password_change_new_password_no_lowercase():
    """Test that new password must contain lowercase."""
    from app.schemas import PasswordChange
    with pytest.raises(ValidationError) as exc:
        PasswordChange(current_password="OldPass123", new_password="UPPERCASE123")
    assert "lowercase letter" in str(exc.value)


def test_password_change_new_password_no_digit():
    """Test that new password must contain a digit."""
    from app.schemas import PasswordChange
    with pytest.raises(ValidationError) as exc:
        PasswordChange(current_password="OldPass123", new_password="NoDigitsHere")
    assert "digit" in str(exc.value)


def test_password_change_same_as_current():
    """Test that new password cannot be same as current password."""
    from app.schemas import PasswordChange
    with pytest.raises(ValidationError) as exc:
        PasswordChange(current_password="SamePass123", new_password="SamePass123")
    assert "must be different" in str(exc.value)


# =================================================================
# Email Change Schema Tests
# =================================================================

def test_email_change_validation_success():
    """Test that valid email change passes validation."""
    from app.schemas import EmailChange
    email_change = EmailChange(
        new_email="newemail@example.com",
        password="CurrentPass123"
    )
    assert email_change.new_email == "newemail@example.com"
    assert email_change.password == "CurrentPass123"


def test_email_change_invalid_email():
    """Test that invalid email format is rejected."""
    from app.schemas import EmailChange
    with pytest.raises(ValidationError) as exc:
        EmailChange(new_email="notanemail", password="CurrentPass123")
    assert "email" in str(exc.value).lower()


# =================================================================
# Account Delete Schema Tests
# =================================================================

def test_account_delete_validation_success():
    """Test that valid account delete passes validation."""
    from app.schemas import AccountDelete
    delete_req = AccountDelete(password="CurrentPass123", confirm_deletion=True)
    assert delete_req.password == "CurrentPass123"
    assert delete_req.confirm_deletion is True


def test_account_delete_confirmation_required():
    """Test that account deletion requires confirmation."""
    from app.schemas import AccountDelete
    with pytest.raises(ValidationError) as exc:
        AccountDelete(password="CurrentPass123", confirm_deletion=False)
    assert "must confirm" in str(exc.value)


# =================================================================
# Additional UserCreate Validation Tests
# =================================================================

def test_user_create_email_valid_formats():
    """Test various valid email formats."""
    valid_emails = [
        "user@example.com",
        "user.name@example.com",
        "user+tag@example.com",
        "user@subdomain.example.com",
    ]
    for email in valid_emails:
        user = UserCreate(email=email, password="ValidPass123")
        assert user.email == email


def test_user_create_password_minimum_length():
    """Test that password with exactly 8 characters is accepted."""
    user = UserCreate(email="test@example.com", password="Valid123")
    assert len(user.password) == 8


def test_user_create_password_maximum_length():
    """Test that password up to 100 characters is accepted."""
    long_password = "A" * 49 + "a" * 49 + "12"  # 100 chars with upper, lower, digit
    user = UserCreate(email="test@example.com", password=long_password)
    assert len(user.password) == 100


def test_user_create_password_too_long():
    """Test that password exceeding 100 characters is rejected."""
    long_password = "A" * 50 + "a" * 50 + "123"  # 103 chars
    with pytest.raises(ValidationError) as exc:
        UserCreate(email="test@example.com", password=long_password)
    assert "at most 100 characters" in str(exc.value)


def test_user_create_invalid_email_formats():
    """Test various invalid email formats."""
    invalid_emails = [
        "notanemail",
        "@example.com",
        "user@",
        "user@.com",
    ]
    for email in invalid_emails:
        with pytest.raises(ValidationError):
            UserCreate(email=email, password="ValidPass123")


# =================================================================
# Additional Password Change Schema Tests
# =================================================================

def test_password_change_new_password_minimum_length():
    """Test that new password with exactly 8 characters is accepted."""
    from app.schemas import PasswordChange
    pwd_change = PasswordChange(
        current_password="OldPass123",
        new_password="NewPass1"
    )
    assert len(pwd_change.new_password) == 8


def test_password_change_complex_password():
    """Test that complex password with special chars passes."""
    from app.schemas import PasswordChange
    pwd_change = PasswordChange(
        current_password="OldPass123",
        new_password="Complex1Pass!"
    )
    assert pwd_change.new_password == "Complex1Pass!"