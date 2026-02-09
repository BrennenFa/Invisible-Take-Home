import pytest
import uuid


def test_deposit_success(authenticated_client):
    """Test successful deposit transaction."""
    client, headers, user_data = authenticated_client

    # Create account
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    # Deposit money (needs Idempotency-Key)
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={
            "account_id": account_id,
            "amount": 100.0,
            "description": "Test deposit"
        }
    )

    assert response.status_code == 201, f"Deposit failed: {response.text}"
    transaction = response.json()
    assert transaction["amount"] == 100.0
    assert transaction["type"] == "CREDIT"
    assert transaction["category"] == "DEPOSIT"

    # Verify account balance increased
    acc_response = client.get(f"/accounts/{account_id}", headers=headers)
    assert acc_response.json()["balance"] == 100.0


def test_deposit_negative_amount(authenticated_client):
    """Test deposit fails with negative amount."""
    client, headers, user_data = authenticated_client

    # Create account
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    # Try deposit with negative amount
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={
            "account_id": account_id,
            "amount": -50.0,
            "description": "Bad deposit"
        }
    )

    assert response.status_code == 422, f"Expected validation error: {response.text}"


def test_deposit_nonexistent_account(authenticated_client):
    """Test deposit fails with nonexistent account."""
    client, headers, user_data = authenticated_client

    fake_account_id = str(uuid.uuid4())
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={
            "account_id": fake_account_id,
            "amount": 100.0,
            "description": "Test deposit"
        }
    )

    assert response.status_code == 404, f"Expected 404: {response.text}"


def test_withdrawal_success(authenticated_client):
    """Test successful withdrawal transaction."""
    client, headers, user_data = authenticated_client

    # Create account and deposit money
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 200.0, "description": "Initial deposit"}
    )

    # Withdrawal
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/withdrawal",
        headers=headers_with_idem,
        json={
            "account_id": account_id,
            "amount": 50.0,
            "description": "Test withdrawal"
        }
    )

    assert response.status_code == 201, f"Withdrawal failed: {response.text}"
    transaction = response.json()
    assert transaction["amount"] == 50.0
    assert transaction["type"] == "DEBIT"
    assert transaction["category"] == "WITHDRAWAL"

    # Verify balance
    acc_response = client.get(f"/accounts/{account_id}", headers=headers)
    assert acc_response.json()["balance"] == 150.0


def test_withdrawal_insufficient_funds(authenticated_client):
    """Test withdrawal fails with insufficient funds."""
    client, headers, user_data = authenticated_client

    # Create account with only $50
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 50.0, "description": "Initial deposit"}
    )

    # Try to withdraw $100
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/withdrawal",
        headers=headers_with_idem,
        json={
            "account_id": account_id,
            "amount": 100.0,
            "description": "Too much"
        }
    )

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "Insufficient funds" in response.json()["detail"]


def test_withdrawal_frozen_account(authenticated_client):
    """Test withdrawal fails on frozen account."""
    client, headers, user_data = authenticated_client

    # Create and fund account
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 100.0}
    )

    # Freeze account
    client.patch(f"/accounts/{account_id}/freeze", headers=headers)

    # Try to withdraw
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/withdrawal",
        headers=headers_with_idem,
        json={
            "account_id": account_id,
            "amount": 50.0,
            "description": "Test withdrawal"
        }
    )

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "not active" in response.json()["detail"].lower()


def test_card_payment_success(authenticated_client):
    """Test successful card payment transaction."""
    client, headers, user_data = authenticated_client

    # Create account and card
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    # Fund account
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 500.0}
    )

    # Create card
    card_response = client.post(
        "/cards",
        headers=headers,
        json={
            "account_id": account_id,
            "card_holder_name": "Test User",
            "pin": "1234",
            "card_type": "DEBIT"
        }
    )
    card_id = card_response.json()["id"]

    # Make payment
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/card-payment",
        headers=headers_with_idem,
        json={
            "card_id": card_id,
            "amount": 75.0,
            "description": "Test payment",
            "merchant": "Test Merchant"
        }
    )

    assert response.status_code == 201, f"Card payment failed: {response.text}"
    transaction = response.json()
    assert transaction["amount"] == 75.0
    assert transaction["type"] == "DEBIT"
    assert transaction["category"] == "CARD_PAYMENT"
    assert transaction["card_id"] == card_id


def test_card_payment_insufficient_funds(authenticated_client):
    """Test card payment fails with insufficient funds."""
    client, headers, user_data = authenticated_client

    # Create account with only $50
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 50.0}
    )

    # Create card
    card_response = client.post(
        "/cards",
        headers=headers,
        json={
            "account_id": account_id,
            "card_holder_name": "Test User",
            "pin": "1234",
            "card_type": "DEBIT"
        }
    )
    card_id = card_response.json()["id"]

    # Try to pay $100
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/card-payment",
        headers=headers_with_idem,
        json={
            "card_id": card_id,
            "amount": 100.0,
            "merchant": "Test Merchant"
        }
    )

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "Insufficient funds" in response.json()["detail"]


def test_card_payment_cancelled_card(authenticated_client):
    """Test card payment fails with cancelled card."""
    client, headers, user_data = authenticated_client

    # Create account and card
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 500.0}
    )

    card_response = client.post(
        "/cards",
        headers=headers,
        json={
            "account_id": account_id,
            "card_holder_name": "Test User",
            "pin": "1234",
            "card_type": "DEBIT"
        }
    )
    card_id = card_response.json()["id"]

    # Cancel card
    client.delete(f"/cards/{card_id}", headers=headers)

    # Try to pay with cancelled card
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    response = client.post(
        "/transactions/card-payment",
        headers=headers_with_idem,
        json={
            "card_id": card_id,
            "amount": 50.0,
            "merchant": "Test Merchant"
        }
    )

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "cancelled" in response.json()["detail"].lower()


def test_get_transactions_for_account(authenticated_client):
    """Test retrieving transactions for an account."""
    client, headers, user_data = authenticated_client

    # Create account
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    # Make multiple transactions
    for i in range(3):
        headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
        client.post(
            "/transactions/deposit",
            headers=headers_with_idem,
            json={"account_id": account_id, "amount": (i + 1) * 10.0}
        )

    # Get transactions
    response = client.get(
        "/transactions?account_id=" + account_id,
        headers=headers
    )

    assert response.status_code == 200, f"Get transactions failed: {response.text}"
    transactions = response.json()
    assert len(transactions) == 3
    assert all(t["account_id"] == account_id for t in transactions)


def test_transactions_unauthenticated(client):
    """Test transaction endpoints fail without authentication."""
    account_id = str(uuid.uuid4())

    # Deposit
    response = client.post(
        "/transactions/deposit",
        json={"account_id": account_id, "amount": 100.0}
    )
    assert response.status_code == 401, f"Expected 401: {response.text}"

    # Withdrawal
    response = client.post(
        "/transactions/withdrawal",
        json={"account_id": account_id, "amount": 50.0}
    )
    assert response.status_code == 401, f"Expected 401: {response.text}"

    # Card payment
    response = client.post(
        "/transactions/card-payment",
        json={"card_id": str(uuid.uuid4()), "amount": 50.0}
    )
    assert response.status_code == 401, f"Expected 401: {response.text}"

    # Get transactions
    response = client.get("/transactions")
    assert response.status_code == 401, f"Expected 401: {response.text}"
