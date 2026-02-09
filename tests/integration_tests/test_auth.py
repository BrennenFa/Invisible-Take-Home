import pytest
import uuid


@pytest.fixture
def user_data():
    """Generates a unique email and password for each test run."""
    random_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test_{random_id}@gmail.com",
        "password": "Password2"
    }

def test_auth_workflow(client, user_data):
    """
    Tests the full authentication flow:
    1. Signup
    2. Login (retrieve token)
    3. Get 'Me' endpoint (verify token works)
    """
    
    # Sign up
    signup_response = client.post("/auth/signup", json=user_data)
    
    assert signup_response.status_code in [200, 201], \
        f"Signup failed: {signup_response.text}"

    # Login
    login_response = client.post("/auth/login", json=user_data)
    
    assert login_response.status_code == 200, \
        f"Login failed: {login_response.text}"
    
    login_json = login_response.json()
    
    assert "access_token" in login_json, "Response did not contain 'access_token'"
    token = login_json["access_token"]
    
    # Validate login with get me route
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    me_response = client.get("/auth/me", headers=headers)
    
    assert me_response.status_code == 200, \
        f"Get Me failed: {me_response.text}"
    
    # Verify the data returned matches the user we created
    me_json = me_response.json()
    assert me_json["email"] == user_data["email"]


def test_password_change_success(authenticated_client):
    """Test successful password change."""
    client, headers, user_data = authenticated_client

    response = client.patch(
        "/auth/password",
        headers=headers,
        json={
            "current_password": user_data["password"],
            "new_password": "NewPassword456"
        }
    )

    assert response.status_code == 200
    assert "Password changed successfully" in response.json()["message"]

    # Verify old password no longer works
    login_response = client.post(
        "/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]}
    )
    assert login_response.status_code == 401

    # Verify new password works
    login_response = client.post(
        "/auth/login",
        json={"email": user_data["email"], "password": "NewPassword456"}
    )
    assert login_response.status_code == 200


def test_password_change_wrong_current_password(authenticated_client):
    """Test password change fails with wrong current password."""
    client, headers, user_data = authenticated_client

    response = client.patch(
        "/auth/password",
        headers=headers,
        json={
            "current_password": "WrongPassword123",
            "new_password": "NewPassword456"
        }
    )
    assert response.status_code == 401


def test_password_change_same_as_current(authenticated_client):
    """Test password change fails when new password is same as current."""
    client, headers, user_data = authenticated_client

    response = client.patch(
        "/auth/password",
        headers=headers,
        json={
            "current_password": user_data["password"],
            "new_password": user_data["password"]
        }
    )
    assert response.status_code == 422


def test_password_change_invalid_format(authenticated_client):
    """Test password change fails with invalid password format."""
    client, headers, user_data = authenticated_client

    response = client.patch(
        "/auth/password",
        headers=headers,
        json={
            "current_password": user_data["password"],
            "new_password": "short"
        }
    )
    assert response.status_code == 422


def test_password_change_unauthenticated(client):
    """Test password change fails without authentication."""
    response = client.patch(
        "/auth/password",
        json={"current_password": "Pass", "new_password": "New"}
    )
    assert response.status_code == 401


def test_email_change_success(authenticated_client):
    """Test successful email change."""
    client, headers, user_data = authenticated_client
    new_email = f"new_{uuid.uuid4().hex[:6]}@example.com"

    response = client.patch(
        "/auth/email",
        headers=headers,
        json={"new_email": new_email, "password": user_data["password"]}
    )

    assert response.status_code == 200
    assert response.json()["email"] == new_email

    login_response = client.post(
        "/auth/login",
        json={"email": new_email, "password": user_data["password"]}
    )
    assert login_response.status_code == 200


def test_email_change_duplicate_email(authenticated_client):
    """Test email change fails if new email already exists."""
    client, headers, user_data = authenticated_client

    # 1. Create a SECOND user in the system
    other_email = f"taken_{uuid.uuid4().hex[:6]}@test.com"
    signup_payload = {
        "email": other_email,
        "password": "OtherPassword123"
    }
    signup_res = client.post("/auth/signup", json=signup_payload)
    assert signup_res.status_code in [200, 201], "Failed to create setup user"

    # 2. Try to change the FIRST user's email to the SECOND user's email
    response = client.patch(
        "/auth/email",
        headers=headers,
        json={
            "new_email": other_email, # This email is now taken
            "password": user_data["password"]
        }
    )

    # This should now trigger the 400 "Email already in use" error
    assert response.status_code == 400, f"Expected 400 but got {response.status_code}: {response.text}"
    assert "Email already in use" in response.json()["detail"]

def test_email_change_unauthenticated(client):
    """Test email change fails without authentication."""
    response = client.patch(
        "/auth/email",
        json={"new_email": "new@example.com", "password": "Pass"}
    )
    assert response.status_code == 401


def test_account_delete_success(authenticated_client):
    """Test successful account deletion."""
    client, headers, user_data = authenticated_client

    response = client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={"password": user_data["password"], "confirm_deletion": True}
    )

    assert response.status_code == 200
    result = response.json()
    assert "Account successfully deleted" in result["message"]

    # Original email should now return 401
    login_response = client.post(
        "/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]}
    )
    assert login_response.status_code == 401


def test_account_delete_with_accounts_and_cards(authenticated_client):
    """Test account deletion closes accounts and cancels cards."""
    client, headers, user_data = authenticated_client

    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    client.post(
        "/cards",
        headers=headers,
        json={
            "account_id": account_id,
            "card_holder_name": "Test User",
            "pin": "1234",
            "card_type": "DEBIT"
        }
    )

    response = client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={"password": user_data["password"], "confirm_deletion": True}
    )

    assert response.status_code == 200
    assert response.json()["accounts_closed"] == 1
    assert response.json()["cards_cancelled"] == 1


def test_account_delete_with_balance_fails(authenticated_client):
    """Test account deletion fails if account has balance."""
    client, headers, user_data = authenticated_client

    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 100.0, "description": "test"}
    )

    response = client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={"password": user_data["password"], "confirm_deletion": True}
    )
    assert response.status_code == 400


def test_account_delete_wrong_password(authenticated_client):
    """Test account deletion fails with wrong password."""
    client, headers, user_data = authenticated_client

    response = client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={"password": "WrongPassword123", "confirm_deletion": True}
    )
    assert response.status_code == 401


def test_account_delete_unauthenticated(client):
    """Test account deletion fails without authentication."""
    response = client.request(
        "DELETE",
        "/auth/account",
        json={"password": "Password123", "confirm_deletion": True}
    )
    assert response.status_code == 401


# ========== ADDITIONAL SIGNUP VALIDATION TESTS ==========

def test_signup_password_no_uppercase(client):
    """Test that password without uppercase letter is rejected."""
    user_data = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "password1"
    }
    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 422
    assert "uppercase" in response.text.lower()


def test_signup_password_no_lowercase(client):
    """Test that password without lowercase letter is rejected."""
    user_data = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "PASSWORD1"
    }
    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 422
    assert "lowercase" in response.text.lower()


def test_signup_password_no_digit(client):
    """Test that password without digit is rejected."""
    user_data = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "PasswordNoDigit"
    }
    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 422
    assert "digit" in response.text.lower()


def test_signup_password_too_short(client):
    """Test that password shorter than 8 characters is rejected."""
    user_data = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "Pass1"
    }
    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 422


def test_signup_invalid_email_format(client):
    """Test that invalid email format is rejected."""
    user_data = {
        "email": "not-an-email",
        "password": "ValidPass1"
    }
    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 422


def test_login_with_deleted_account(client):
    """Test that logging into a deleted account fails."""
    user_data = {
        "email": f"deleted_{uuid.uuid4().hex[:8]}@example.com",
        "password": "SecurePass1"
    }

    # Signup and get token
    signup_res = client.post("/auth/signup", json=user_data)
    token = signup_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Delete account
    client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={"password": user_data["password"], "confirm_deletion": True}
    )

    # Try to login
    response = client.post("/auth/login", json=user_data)
    assert response.status_code == 401


def test_email_change_wrong_password(authenticated_client):
    """Test email change fails with wrong password."""
    client, headers, _ = authenticated_client

    response = client.patch(
        "/auth/email",
        headers=headers,
        json={
            "new_email": f"new_{uuid.uuid4().hex[:8]}@example.com",
            "password": "WrongPassword123"
        }
    )
    assert response.status_code == 401