import pytest


# ========== AUTHENTICATED TESTS ==========

def test_create_account_authenticated(authenticated_client):
    """Test creating an account with valid authentication."""
    client, headers, user_data = authenticated_client

    account_data = {
        "type": "CHECKING"
    }

    response = client.post("/accounts", headers=headers, json=account_data)

    assert response.status_code == 201, f"Account creation failed: {response.text}"

    account = response.json()
    assert account["type"] == "CHECKING"
    assert account["balance"] == 0.0
    assert account["status"] == "ACTIVE"
    assert "id" in account


def test_get_accounts_authenticated(authenticated_client):
    """Test getting accounts list with valid authentication."""
    client, headers, user_data = authenticated_client

    # Create one of each account type
    client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    client.post("/accounts", headers=headers, json={"type": "SAVINGS"})

    # Get all accounts
    response = client.get("/accounts", headers=headers)

    assert response.status_code == 200, f"Get accounts failed: {response.text}"

    accounts = response.json()
    assert len(accounts) == 2
    assert accounts[0]["type"] in ["CHECKING", "SAVINGS"]
    assert accounts[1]["type"] in ["CHECKING", "SAVINGS"]


def test_get_specific_account_authenticated(authenticated_client):
    """Test getting a specific account by ID with valid authentication."""
    client, headers, user_data = authenticated_client

    # Create an account
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    # Get the specific account
    response = client.get(f"/accounts/{account_id}", headers=headers)

    assert response.status_code == 200, f"Get account failed: {response.text}"

    account = response.json()
    assert account["id"] == account_id
    assert account["type"] == "CHECKING"


def test_get_account_transactions_authenticated(authenticated_client):
    """Test getting transactions for an account with valid authentication."""
    client, headers, user_data = authenticated_client

    # Create an account
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    # Get transactions (should be empty)
    response = client.get(f"/accounts/{account_id}/transactions", headers=headers)

    assert response.status_code == 200, f"Get transactions failed: {response.text}"

    transactions = response.json()
    assert isinstance(transactions, list)


def test_freeze_account_authenticated(authenticated_client):
    """Test freezing an account successfully."""
    client, headers, user_data = authenticated_client

    # Create an account
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    # Freeze the account
    response = client.patch(f"/accounts/{account_id}/freeze", headers=headers)

    assert response.status_code == 200, f"Freeze failed: {response.text}"
    account = response.json()
    assert account["status"] == "FROZEN"

    # Verify account is frozen
    get_response = client.get(f"/accounts/{account_id}", headers=headers)
    assert get_response.json()["status"] == "FROZEN"


def test_unfreeze_account_authenticated(authenticated_client):
    """Test unfreezing a frozen account."""
    client, headers, user_data = authenticated_client

    # Create and freeze an account
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    client.patch(f"/accounts/{account_id}/freeze", headers=headers)

    # Unfreeze the account
    response = client.patch(f"/accounts/{account_id}/unfreeze", headers=headers)

    assert response.status_code == 200, f"Unfreeze failed: {response.text}"
    account = response.json()
    assert account["status"] == "ACTIVE"


def test_freeze_already_frozen_account(authenticated_client):
    """Test freezing an already frozen account fails."""
    client, headers, user_data = authenticated_client

    # Create and freeze an account
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    client.patch(f"/accounts/{account_id}/freeze", headers=headers)

    # Try to freeze again
    response = client.patch(f"/accounts/{account_id}/freeze", headers=headers)

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "already frozen" in response.json()["detail"].lower()


def test_unfreeze_active_account(authenticated_client):
    """Test unfreezing an already active account fails."""
    client, headers, user_data = authenticated_client

    # Create an account (already active)
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    # Try to unfreeze
    response = client.patch(f"/accounts/{account_id}/unfreeze", headers=headers)

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "not frozen" in response.json()["detail"].lower()


def test_close_account_authenticated(authenticated_client):
    """Test closing an account with zero balance."""
    client, headers, user_data = authenticated_client

    # Create an account
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    # Close the account
    response = client.patch(f"/accounts/{account_id}/close", headers=headers)

    assert response.status_code == 200, f"Close failed: {response.text}"
    account = response.json()
    assert account["status"] == "CLOSED"


def test_close_account_with_balance_fails(authenticated_client):
    """Test closing an account with balance fails."""
    import uuid
    client, headers, user_data = authenticated_client

    # Create an account and add funds
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 100.0}
    )

    # Try to close account with balance
    response = client.patch(f"/accounts/{account_id}/close", headers=headers)

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "cannot close account with non-zero balance." in response.json()["detail"].lower()


def test_close_already_closed_account(authenticated_client):
    """Test closing an already closed account fails."""
    client, headers, user_data = authenticated_client

    # Create and close an account
    create_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = create_response.json()["id"]

    client.patch(f"/accounts/{account_id}/close", headers=headers)

    # Try to close again
    response = client.patch(f"/accounts/{account_id}/close", headers=headers)

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "already closed" in response.json()["detail"].lower()


# ========== UNAUTHENTICATED TESTS ==========

def test_create_account_unauthenticated(client):
    """Test that creating an account without auth returns 401."""
    account_data = {
        "type": "CHECKING"
    }

    response = client.post("/accounts", json=account_data)

    assert response.status_code == 401, \
        f"Expected 401 for unauthenticated request, got {response.status_code}"


def test_get_accounts_unauthenticated(client):
    """Test that getting accounts without auth returns 401."""
    response = client.get("/accounts")

    assert response.status_code == 401, \
        f"Expected 401 for unauthenticated request, got {response.status_code}"


def test_get_specific_account_unauthenticated(client):
    """Test that getting a specific account without auth returns 401."""

    # Use a fake UUID
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/accounts/{fake_id}")

    assert response.status_code == 401, \
        f"Expected 401 for unauthenticated request, got {response.status_code}"


def test_get_account_transactions_unauthenticated(client):
    """Test that getting account transactions without auth returns 401."""
    # Use a fake UUID
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/accounts/{fake_id}/transactions")

    assert response.status_code == 401, \
        f"Expected 401 for unauthenticated request, got {response.status_code}"


def test_freeze_account_unauthenticated(client):
    """Test that freezing an account without auth returns 401."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.patch(f"/accounts/{fake_id}/freeze")

    assert response.status_code == 401, \
        f"Expected 401 for unauthenticated request, got {response.status_code}"


def test_unfreeze_account_unauthenticated(client):
    """Test that unfreezing an account without auth returns 401."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.patch(f"/accounts/{fake_id}/unfreeze")

    assert response.status_code == 401, \
        f"Expected 401 for unauthenticated request, got {response.status_code}"


def test_close_account_unauthenticated(client):
    """Test that closing an account without auth returns 401."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.patch(f"/accounts/{fake_id}/close")

    assert response.status_code == 401, \
        f"Expected 401 for unauthenticated request, got {response.status_code}"
