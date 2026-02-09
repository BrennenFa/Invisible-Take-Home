"""
Idempotency tests for financial transfers.
Tests exactly-once semantics using database-level idempotency keys.
"""
import pytest
import uuid
import json


def test_duplicate_transfer_same_idempotency_key(authenticated_client):
    """
    Test exactly-once semantics: Sending same request twice with same
    Idempotency-Key should return same transfer and only deduct money once.
    """
    client, headers, _ = authenticated_client

    # Create accounts
    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit initial balance
    client.post(
        "/transactions/deposit",
        headers=headers,
        json={"account_id": source_acc["id"], "amount": 200.0, "description": "Initial deposit"}
    )

    # Create a unique idempotency key
    idempotency_key = str(uuid.uuid4())
    headers_with_idempotency = {**headers, "Idempotency-Key": idempotency_key}

    transfer_data = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": 100.0,
        "description": "Test transfer"
    }

    # First request
    response1 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response1.status_code == 201
    transfer1 = response1.json()
    transfer1_id = transfer1["id"]

    # Verify balances after first transfer
    source_after_1 = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    dest_after_1 = client.get(f"/accounts/{dest_acc['id']}", headers=headers).json()
    assert source_after_1["balance"] == 100.0
    assert dest_after_1["balance"] == 100.0

    # Second request with same idempotency key (simulating retry)
    response2 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response2.status_code == 201
    transfer2 = response2.json()
    transfer2_id = transfer2["id"]

    # Both should return the same transfer ID
    assert transfer1_id == transfer2_id, "Duplicate requests should return the same transfer"

    # Verify balances haven't changed (money not deducted twice)
    source_after_2 = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    dest_after_2 = client.get(f"/accounts/{dest_acc['id']}", headers=headers).json()
    assert source_after_2["balance"] == 100.0, "Balance should not change on duplicate request"
    assert dest_after_2["balance"] == 100.0, "Destination balance should not change on duplicate request"


def test_different_idempotency_keys_create_different_transfers(authenticated_client):
    """
    Test that different idempotency keys create different transfers,
    even with same source, destination, and amount.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit initial balance
    client.post(
        "/transactions/deposit",
        headers=headers,
        json={"account_id": source_acc["id"], "amount": 500.0, "description": "Initial deposit"}
    )

    transfer_data_base = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": 100.0,
        "description": "Test transfer"
    }

    # First transfer with idempotency key 1
    key1 = str(uuid.uuid4())
    headers_with_key1 = {**headers, "Idempotency-Key": key1}
    response1 = client.post("/transfers", headers=headers_with_key1, json=transfer_data_base)
    assert response1.status_code == 201
    transfer1_id = response1.json()["id"]

    # Second transfer with different idempotency key 2
    key2 = str(uuid.uuid4())
    headers_with_key2 = {**headers, "Idempotency-Key": key2}
    response2 = client.post("/transfers", headers=headers_with_key2, json=transfer_data_base)
    assert response2.status_code == 201
    transfer2_id = response2.json()["id"]

    # Different keys should create different transfers
    assert transfer1_id != transfer2_id, "Different idempotency keys should create different transfers"

    # Verify both transfers were executed
    source_after = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    dest_after = client.get(f"/accounts/{dest_acc['id']}", headers=headers).json()
    assert source_after["balance"] == 300.0, "Source balance should decrease by 200 (two $100 transfers)"
    assert dest_after["balance"] == 200.0, "Destination balance should increase by 200"


def test_transfer_without_idempotency_key(authenticated_client):
    """
    Test that transfers work without Idempotency-Key header (optional).
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    client.post(
        "/transactions/deposit",
        headers=headers,
        json={"account_id": source_acc["id"], "amount": 100.0, "description": "Initial deposit"}
    )

    transfer_data = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": 50.0,
        "description": "Transfer without idempotency key"
    }

    response = client.post("/transfers", headers=headers, json=transfer_data)
    assert response.status_code == 201
    assert response.json()["amount"] == 50.0


def test_idempotency_with_network_glitch_simulation(authenticated_client):
    """
    Simulate network glitch: Client sends request, connection drops,
    client retries with same idempotency key. Should return same transfer.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    client.post(
        "/transactions/deposit",
        headers=headers,
        json={"account_id": source_acc["id"], "amount": 300.0, "description": "Initial deposit"}
    )

    idempotency_key = f"network-glitch-{uuid.uuid4()}"
    headers_with_idempotency = {**headers, "Idempotency-Key": idempotency_key}

    transfer_data = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": 75.50,
        "description": "Transfer with network glitch",
    }

    # Original request
    response1 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response1.status_code == 201
    transfer1 = response1.json()

    # Simulate retry after network glitch
    response2 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response2.status_code == 201
    transfer2 = response2.json()

    # Should be same transfer
    assert transfer1["id"] == transfer2["id"]
    assert transfer1["created_at"] == transfer2["created_at"]

    # Verify balance is correct (only one transfer executed)
    source_after = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    dest_after = client.get(f"/accounts/{dest_acc['id']}", headers=headers).json()
    assert source_after["balance"] == 224.50
    assert dest_after["balance"] == 75.50


def test_idempotency_prevents_double_charging(authenticated_client):
    """
    Critical test: Verify idempotency prevents double-charging.
    Client thinks first request failed, retries with same key - money should
    only be transferred once.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    initial_balance = 1000.0
    transfer_amount = 250.0

    client.post(
        "/transactions/deposit",
        headers=headers,
        json={"account_id": source_acc["id"], "amount": initial_balance, "description": "Initial deposit"}
    )

    idempotency_key = f"critical-test-{uuid.uuid4()}"
    headers_with_idempotency = {**headers, "Idempotency-Key": idempotency_key}

    transfer_data = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": transfer_amount,
        "description": "Critical idempotency test",
    }

    # First attempt
    response1 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response1.status_code == 201

    # Second attempt (client thought first failed)
    response2 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response2.status_code == 201

    # Third attempt (client really paranoid)
    response3 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response3.status_code == 201

    # All three should return same transfer ID
    assert response1.json()["id"] == response2.json()["id"] == response3.json()["id"]

    # Verify source balance: should only be deducted once
    source_final = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    expected_balance = initial_balance - transfer_amount
    assert source_final["balance"] == expected_balance, \
        f"Expected {expected_balance}, but got {source_final['balance']}. Money was deducted incorrectly!"

    dest_final = client.get(f"/accounts/{dest_acc['id']}", headers=headers).json()
    assert dest_final["balance"] == transfer_amount, \
        f"Destination should have exactly {transfer_amount}"


def test_failed_transfer_cached_error(authenticated_client):
    """
    Test that failed transfers cache error response.
    Retry with same idempotency key should return same error without re-executing.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit only $50 (not enough for $100 transfer)
    client.post(
        "/transactions/deposit",
        headers=headers,
        json={"account_id": source_acc["id"], "amount": 50.0, "description": "Limited deposit"}
    )

    idempotency_key = f"failed-transfer-{uuid.uuid4()}"
    headers_with_idempotency = {**headers, "Idempotency-Key": idempotency_key}

    transfer_data = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": 100.0,  # More than balance
        "description": "Transfer with insufficient funds",
    }

    # First attempt - should fail
    response1 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response1.status_code == 400
    assert "Insufficient funds" in response1.json()["detail"]

    # Second attempt with same idempotency key
    response2 = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
    assert response2.status_code == 400
    assert response1.json()["detail"] == response2.json()["detail"]

    # Balance should remain unchanged
    source_after = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    assert source_after["balance"] == 50.0


def test_multiple_retries_same_idempotency_key(authenticated_client):
    """
    Test that multiple retries with same idempotency key all return same result.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    client.post(
        "/transactions/deposit",
        headers=headers,
        json={"account_id": source_acc["id"], "amount": 500.0, "description": "Initial deposit"}
    )

    idempotency_key = f"retry-test-{uuid.uuid4()}"
    headers_with_idempotency = {**headers, "Idempotency-Key": idempotency_key}

    transfer_data = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": 100.0,
    }

    # Make 5 requests with same idempotency key
    responses = []
    for i in range(5):
        response = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)
        assert response.status_code == 201
        responses.append(response.json())

    # All should return same transfer ID
    transfer_ids = [r["id"] for r in responses]
    assert len(set(transfer_ids)) == 1, "All requests should return same transfer ID"

    # Verify balance deducted only once
    source_final = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    assert source_final["balance"] == 400.0, "Balance should be deducted only once"
