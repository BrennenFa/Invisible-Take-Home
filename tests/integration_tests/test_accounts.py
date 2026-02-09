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
