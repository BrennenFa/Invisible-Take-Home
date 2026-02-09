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
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    deposit_response = client.post("/transactions/deposit", headers=headers_with_idem, json=deposit_data)
    assert deposit_response.status_code == 201

    # Transfer money from acc1 to acc2
    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_id": acc2["id"],
        "amount": 50.0,
        "description": "Rent payment"
    }

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers", headers=headers_with_idem, json=transfer_data)
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

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers", headers=headers_with_idem, json=transfer_data)
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

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers", headers=headers_with_idem, json=transfer_data)
    # Pydantic validation catches this early with 422
    assert response.status_code == 422
    assert "must be different" in response.text.lower()


def test_get_transfers_list(authenticated_client):
    """Test retrieving transfers for the current user."""
    client, headers, _ = authenticated_client

    response = client.get("/transfers", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_specific_transfer_success(authenticated_client):
    """Test retrieving a specific transfer by ID."""
    client, headers, _ = authenticated_client

    # Create accounts
    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit money
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post("/transactions/deposit", headers=headers_with_idem, json={
        "account_id": acc1["id"],
        "amount": 200.0
    })

    # Create transfer
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    transfer_response = client.post("/transfers", headers=headers_with_idem, json={
        "source_account_id": acc1["id"],
        "destination_account_id": acc2["id"],
        "amount": 50.0,
        "description": "Test transfer"
    })
    assert transfer_response.status_code == 201
    transfer = transfer_response.json()

    # Get specific transfer
    response = client.get(f"/transfers/{transfer['id']}", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == transfer["id"]
    assert data["amount"] == 50.0
    assert data["source_account_id"] == str(acc1["id"])
    assert data["destination_account_id"] == str(acc2["id"])


def test_get_specific_transfer_not_found(authenticated_client):
    """Test retrieving a non-existent transfer returns 404."""
    client, headers, _ = authenticated_client

    fake_id = str(uuid.uuid4())
    response = client.get(f"/transfers/{fake_id}", headers=headers)
    assert response.status_code == 404


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


# ========== TRANSFER BY ACCOUNT NUMBER TESTS ==========

def test_create_transfer_by_account_number_success(authenticated_client):
    """Test successful transfer using account number and routing number."""
    client, headers, user_data = authenticated_client

    # Create source and destination accounts
    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit money into source account
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    deposit_response = client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": acc1["id"], "amount": 500.0}
    )
    assert deposit_response.status_code == 201

    # Transfer by account number using full account number from creation response
    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_number": acc2["account_number"],
        "destination_routing_number": acc2["routing_number"],
        "amount": 150.0,
        "description": "Transfer via account number"
    }

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers/account", headers=headers_with_idem, json=transfer_data)
    assert response.status_code == 201

    # Validate response
    transfer = response.json()
    assert transfer["amount"] == 150.0
    assert transfer["source_account_id"] == str(acc1["id"])
    assert transfer["destination_account_id"] == str(acc2["id"])

    # Validate balances
    acc1_after = client.get(f"/accounts/{acc1['id']}", headers=headers).json()
    acc2_after = client.get(f"/accounts/{acc2['id']}", headers=headers).json()

    assert acc1_after["balance"] == 350.0
    assert acc2_after["balance"] == 150.0


def test_create_transfer_by_account_number_invalid_routing(authenticated_client):
    """Test transfer fails with invalid routing number."""
    client, headers, _ = authenticated_client

    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_number": "123456789",
        "destination_routing_number": "12345",  # Invalid - not 9 digits
        "amount": 100.0
    }

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers/account", headers=headers_with_idem, json=transfer_data)
    assert response.status_code == 422
    assert "Routing number must be 9 digits" in response.text


def test_create_transfer_by_account_number_invalid_account(authenticated_client):
    """Test transfer fails with invalid account number."""
    client, headers, _ = authenticated_client

    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_number": "12",  # Too short
        "destination_routing_number": "123456789",
        "amount": 100.0
    }

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers/account", headers=headers_with_idem, json=transfer_data)
    assert response.status_code == 422
    assert "Invalid account number format" in response.text


def test_create_transfer_by_account_number_not_found(authenticated_client):
    """Test transfer fails when recipient account not found."""
    client, headers, _ = authenticated_client

    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    # Deposit so we have balance
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": acc1["id"], "amount": 100.0}
    )

    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_number": "999999999",  # Non-existent
        "destination_routing_number": "123456789",
        "amount": 50.0
    }

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers/account", headers=headers_with_idem, json=transfer_data)
    assert response.status_code == 404
    assert "Recipient account not found" in response.json()["detail"]


def test_create_transfer_by_account_number_insufficient_funds(authenticated_client):
    """Test transfer fails with insufficient funds."""
    client, headers, _ = authenticated_client

    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_number": acc2["account_number"],
        "destination_routing_number": acc2["routing_number"],
        "amount": 9999.0  # More than balance
    }

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers/account", headers=headers_with_idem, json=transfer_data)
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]


def test_create_transfer_by_account_number_missing_idempotency_key(authenticated_client):
    """Test transfer fails without idempotency key."""
    client, headers, _ = authenticated_client

    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_number": acc2["account_number_masked"].replace("****-****-****-", ""),
        "destination_routing_number": acc2["routing_number"],
        "amount": 50.0
    }

    response = client.post("/transfers/account", headers=headers, json=transfer_data)
    assert response.status_code == 400
    assert "Idempotency-Key header is required" in response.json()["detail"]


def test_create_transfer_by_account_number_unauthenticated(client):
    """Test transfer without auth returns 401."""
    transfer_data = {
        "source_account_id": str(uuid.uuid4()),
        "destination_account_number": "123456789",
        "destination_routing_number": "123456789",
        "amount": 100.0
    }
    response = client.post("/transfers/account", json=transfer_data)
    assert response.status_code == 401


def test_create_transfer_by_account_number_same_account(authenticated_client):
    """Test transfer fails when source and destination are the same."""
    client, headers, _ = authenticated_client

    acc1 = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    # Deposit so we have balance
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": acc1["id"], "amount": 100.0}
    )

    transfer_data = {
        "source_account_id": acc1["id"],
        "destination_account_number": acc1["account_number"],
        "destination_routing_number": acc1["routing_number"],
        "amount": 50.0
    }

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers/account", headers=headers_with_idem, json=transfer_data)
    assert response.status_code == 400
    assert "must be different" in response.json()["detail"]


def test_create_transfer_by_account_number_unauthorized_source(authenticated_client_2):
    """Test transfer fails when user doesn't own source account."""
    client, headers_user1, user1_data = authenticated_client_2

    # User 1 creates account but doesn't own it
    acc1 = client.post("/accounts", headers=headers_user1, json={"type": "CHECKING"}).json()

    # Create another user's account via different headers
    acc2 = client.post("/accounts", headers=headers_user1, json={"type": "SAVINGS"}).json()

    # Deposit to user 1's account
    headers_with_idem = {**headers_user1, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": acc2["id"], "amount": 100.0}
    )

    # Try to transfer from a user we don't own
    transfer_data = {
        "source_account_id": str(uuid.uuid4()),  # Fake account
        "destination_account_number": acc2["account_number_masked"].replace("****-****-****-", ""),
        "destination_routing_number": acc2["routing_number"],
        "amount": 50.0
    }

    headers_with_idem = {**headers_user1, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post("/transfers/account", headers=headers_with_idem, json=transfer_data)
    assert response.status_code == 404
