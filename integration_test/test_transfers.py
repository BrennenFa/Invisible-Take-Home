import pytest
import uuid

# ========== AUTHENTICATED TESTS ==========

def test_create_transfer_success(authenticated_client):
    """Test successful transfer between two valid accounts."""
    client, headers, user_data = authenticated_client

    # Create source and destination accounts
    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit money into source account
    deposit_data = {
        "account_id": acc1["id"],
        "amount": 100.0,
        "description": "Initial deposit"
    }
    deposit_response = client.post("/transactions/deposit", headers=headers, json=deposit_data)
    assert deposit_response.status_code == 201

    # Transfer money from acc1 to acc2
    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_id": acc2["id"],
        "amount": 50.0,
        "description": "Rent payment"
    }

    response = client.post("/transfers", headers=headers, json=transfer_data)
    assert response.status_code == 201

    # Validate balances after transfer
    acc1_after = client.get(f"/accounts/{acc1['id']}", headers=headers).json()
    acc2_after = client.get(f"/accounts/{acc2['id']}", headers=headers).json()

    assert acc1_after["balance"] == 50.0
    assert acc2_after["balance"] == 50.0 


def test_transfer_insufficient_funds(authenticated_client):
    """Test transfer fails when balance is too low."""
    client, headers, _ = authenticated_client

    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # attempt to transfer more than balance
    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_id": acc2["id"],
        "amount": 999999.0,
        "description": "Too expensive"
    }

    response = client.post("/transfers", headers=headers, json=transfer_data)
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]


def test_transfer_to_same_account(authenticated_client):
    """Test that source and destination cannot be the same."""
    client, headers, _ = authenticated_client
    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_id": acc1["id"],
        "amount": 10.0
    }

    response = client.post("/transfers", headers=headers, json=transfer_data)
    assert response.status_code == 400
    assert "must be different" in response.json()["detail"]


def test_get_transfers_list(authenticated_client):
    """Test retrieving transfers for the current user."""
    client, headers, _ = authenticated_client
    
    response = client.get("/transfers", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ========== UNAUTHENTICATED TESTS ==========

def test_create_transfer_unauthenticated(client):
    """Test that creating a transfer without auth returns 401."""
    transfer_data = {
        "source_account_id": str(uuid.uuid4()),
        "destination_account_id": str(uuid.uuid4()),
        "amount": 100.0
    }
    response = client.post("/transfers", json=transfer_data)
    assert response.status_code == 401


def test_get_transfers_unauthenticated(client):
    """Test that fetching transfers without auth returns 401."""
    response = client.get("/transfers")
    assert response.status_code == 401


def test_get_specific_transfer_unauthenticated(client):
    """Test that fetching a specific transfer without auth returns 401."""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/transfers/{fake_id}")
    assert response.status_code == 401
