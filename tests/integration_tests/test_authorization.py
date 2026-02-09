import pytest
import uuid
import json as json_lib


def test_user_cannot_access_other_users_accounts(client):
    """Test that User A cannot access User B's accounts."""
    # Create User A
    user_a_data = {
        "email": "usera@example.com",
        "password": "PasswordA123"
    }
    client.post("/auth/signup", json=user_a_data)
    login_a = client.post("/auth/login", json=user_a_data)
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}

    # Create User B
    user_b_data = {
        "email": "userb@example.com",
        "password": "PasswordB123"
    }
    client.post("/auth/signup", json=user_b_data)
    login_b = client.post("/auth/login", json=user_b_data)
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}

    # User A creates an account
    acc_response = client.post("/accounts", headers=headers_a, json={"type": "CHECKING"})
    account_a_id = acc_response.json()["id"]

    # User B tries to access User A's account
    response = client.get(f"/accounts/{account_a_id}", headers=headers_b)

    assert response.status_code == 404, f"Expected 404: {response.text}"
    assert "Account not found" in response.json()["detail"]


def test_user_cannot_transfer_from_other_users_account(client):
    """Test that User A cannot transfer from User B's account."""
    # Create User A
    user_a_data = {
        "email": "usera@example.com",
        "password": "PasswordA123"
    }
    client.post("/auth/signup", json=user_a_data)
    login_a = client.post("/auth/login", json=user_a_data)
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}

    # Create User B
    user_b_data = {
        "email": "userb@example.com",
        "password": "PasswordB123"
    }
    client.post("/auth/signup", json=user_b_data)
    login_b = client.post("/auth/login", json=user_b_data)
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}

    # User A creates and funds account A
    acc_a = client.post("/accounts", headers=headers_a, json={"type": "CHECKING"}).json()
    account_a_id = acc_a["id"]

    headers_a_with_idem = {**headers_a, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_a_with_idem,
        json={"account_id": account_a_id, "amount": 200.0}
    )

    # User B creates account B
    acc_b = client.post("/accounts", headers=headers_b, json={"type": "CHECKING"}).json()
    account_b_id = acc_b["id"]

    # User B tries to transfer from User A's account to User B's account
    headers_b_with_idem = {**headers_b, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transfers",
        headers=headers_b_with_idem,
        json={
            "source_account_id": account_a_id,
            "destination_account_id": account_b_id,
            "amount": 50.0
        }
    )

    assert response.status_code == 403, f"Expected 403: {response.text}"
    assert "you do not have permission" in response.json()["detail"].lower()


def test_user_can_transfer_to_other_users_account(client):
    """Test that User A CAN transfer to User B's account (inter-user transfers allowed)."""
    # Create User A
    user_a_data = {
        "email": "usera@example.com",
        "password": "PasswordA123"
    }
    client.post("/auth/signup", json=user_a_data)
    login_a = client.post("/auth/login", json=user_a_data)
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}

    # Create User B
    user_b_data = {
        "email": "userb@example.com",
        "password": "PasswordB123"
    }
    client.post("/auth/signup", json=user_b_data)
    login_b = client.post("/auth/login", json=user_b_data)
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}

    # User A creates and funds account A
    acc_a = client.post("/accounts", headers=headers_a, json={"type": "CHECKING"}).json()
    account_a_id = acc_a["id"]

    headers_a_with_idem = {**headers_a, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_a_with_idem,
        json={"account_id": account_a_id, "amount": 200.0}
    )

    # User B creates account B
    acc_b = client.post("/accounts", headers=headers_b, json={"type": "CHECKING"}).json()
    account_b_id = acc_b["id"]

    # User A transfers to User B's account (should succeed)
    headers_a_with_idem = {**headers_a, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transfers",
        headers=headers_a_with_idem,
        json={
            "source_account_id": account_a_id,
            "destination_account_id": account_b_id,
            "amount": 50.0
        }
    )

    assert response.status_code == 201, f"Expected 201: {response.text}"

    # Verify balances
    acc_a_after = client.get(f"/accounts/{account_a_id}", headers=headers_a).json()
    acc_b_after = client.get(f"/accounts/{account_b_id}", headers=headers_b).json()

    assert acc_a_after["balance"] == 150.0, "User A should have 150 after sending 50"
    assert acc_b_after["balance"] == 50.0, "User B should have 50 after receiving"


def test_user_cannot_operate_on_other_users_card(client):
    """Test that User A cannot operate on User B's card."""
    # Create User A
    user_a_data = {
        "email": "usera@example.com",
        "password": "PasswordA123"
    }
    client.post("/auth/signup", json=user_a_data)
    login_a = client.post("/auth/login", json=user_a_data)
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}

    # Create User B
    user_b_data = {
        "email": "userb@example.com",
        "password": "PasswordB123"
    }
    client.post("/auth/signup", json=user_b_data)
    login_b = client.post("/auth/login", json=user_b_data)
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}

    # User A creates account and card
    acc_a = client.post("/accounts", headers=headers_a, json={"type": "CHECKING"}).json()
    account_a_id = acc_a["id"]

    card_a = client.post(
        "/cards",
        headers=headers_a,
        json={
            "account_id": account_a_id,
            "card_holder_name": "User A",
            "pin": "1234",
            "card_type": "DEBIT"
        }
    ).json()
    card_a_id = card_a["id"]

    # User B tries to freeze User A's card
    response = client.patch(f"/cards/{card_a_id}/freeze", headers=headers_b)

    assert response.status_code == 404, f"Expected 404: {response.text}"


def test_user_cannot_view_other_users_statements(client):
    """Test that User A cannot view User B's statements."""
    # Create User A
    user_a_data = {
        "email": "usera@example.com",
        "password": "PasswordA123"
    }
    client.post("/auth/signup", json=user_a_data)
    login_a = client.post("/auth/login", json=user_a_data)
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}

    # Create User B
    user_b_data = {
        "email": "userb@example.com",
        "password": "PasswordB123"
    }
    client.post("/auth/signup", json=user_b_data)
    login_b = client.post("/auth/login", json=user_b_data)
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}

    # User A creates account
    acc_a = client.post("/accounts", headers=headers_a, json={"type": "CHECKING"}).json()
    account_a_id = acc_a["id"]

    # User B tries to view User A's statement
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    start_date = (now - timedelta(days=1)).isoformat()
    end_date = (now + timedelta(days=1)).isoformat()

    response = client.get(
        f"/statements/account/{account_a_id}?start_date={start_date}&end_date={end_date}&format=json",
        headers=headers_b
    )

    assert response.status_code == 404, f"Expected 404: {response.text}"


def test_user_cannot_view_other_users_transactions(client):
    """Test that User A cannot view User B's transactions."""
    # Create User A
    user_a_data = {
        "email": "usera@example.com",
        "password": "PasswordA123"
    }
    client.post("/auth/signup", json=user_a_data)
    login_a = client.post("/auth/login", json=user_a_data)
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}

    # Create User B
    user_b_data = {
        "email": "userb@example.com",
        "password": "PasswordB123"
    }
    client.post("/auth/signup", json=user_b_data)
    login_b = client.post("/auth/login", json=user_b_data)
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}

    # User A creates account and transaction
    acc_a = client.post("/accounts", headers=headers_a, json={"type": "CHECKING"}).json()
    account_a_id = acc_a["id"]

    headers_a_with_idem = {**headers_a, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_a_with_idem,
        json={"account_id": account_a_id, "amount": 100.0}
    )

    # User B tries to view User A's transactions
    response = client.get(
        f"/transactions?account_id={account_a_id}",
        headers=headers_b
    )

    # Should either return 404 or empty list, not the actual transactions
    assert response.status_code in [404, 200], f"Unexpected status: {response.text}"
    if response.status_code == 200:
        assert len(response.json()) == 0, "Should not see other user's transactions"


def test_deleted_user_cannot_login(authenticated_client, client):
    """Test that deleted user cannot login."""
    user_client, headers, user_data = authenticated_client

    # Delete account
    user_client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={
            "password": user_data["password"],
            "confirm_deletion": True
        }
    )

    # Try to login with deleted account
    response = client.post(
        "/auth/login",
        json=user_data
    )

    # Should fail - either 401 (invalid credentials) or 403 (account deleted)
    assert response.status_code in [401, 403], f"Expected 401 or 403: {response.text}"


def test_deleted_user_cannot_use_token(authenticated_client):
    """Test that deleted user's existing token becomes invalid."""
    user_client, headers, user_data = authenticated_client

    # Delete account
    user_client.request(
        "DELETE",
        "/auth/account",
        headers=headers,
        json={
            "password": user_data["password"],
            "confirm_deletion": True
        }
    )

    # Try to use existing token
    response = user_client.get("/auth/me", headers=headers)

    assert response.status_code == 403, f"Expected 403: {response.text}"
    assert "deleted" in response.json()["detail"].lower()
