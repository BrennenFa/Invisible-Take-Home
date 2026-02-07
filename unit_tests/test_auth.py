import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, Request
from uuid import uuid4
from datetime import datetime, timezone

# Import the code to be tested
from app.routes.auth import signup, login
from app.models import User
from app.schemas import UserCreate

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
    
    user_in = UserCreate(email="new@example.com", password="password123")

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
    
    user_in = UserCreate(email="exists@test.com", password="password123")

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
    
    user_in = UserCreate(email="user@test.com", password="correct_password")

    response = login(request=mock_request, user=user_in, db=mock_db)
    
    # validate token return
    assert response["access_token"] == "login-token"
    mock_verify_pw.assert_called_once_with("correct_password", "hashed_stuff")


def test_login_invalid_credentials():
    """Test login fails for missing user."""
    mock_db = MagicMock()
    
    # Simulate: User not found
    mock_db.execute().scalar_one_or_none.return_value = None
    
    user_in = UserCreate(email="wrong@test.com", password="password")

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
    
    user_in = UserCreate(email="user@test.com", password="the_wrong_password")

    # Calling login with wrong password should raise a 401 Unauthorized
    with pytest.raises(HTTPException) as exc:
        login(request=mock_request, user=user_in, db=mock_db)
    
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid credentials"