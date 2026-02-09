"""
Concurrency tests for financial transfers with idempotency.
Tests that concurrent requests with same idempotency key are handled safely.
"""
import pytest
import threading
import time
import uuid


def test_concurrent_transfers_different_destinations(authenticated_client):
    """
    Test concurrent transfers from same source to different destinations.
    Both should succeed and balances should be correct.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc1 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()
    dest_acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit initial balance
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": source_acc["id"], "amount": 250.0, "description": "Initial deposit"}
    )

    results = []
    lock = threading.Lock()

    def make_transfer(dest_account, transfer_id):
        """Helper to make transfer in thread."""
        try:
            transfer_data = {
                "source_account_id": source_acc["id"],
                "destination_account_id": dest_account["id"],
                "amount": 100.0,
            }
            # Each transfer needs unique idempotency key
            headers_with_transfer_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
            response = client.post("/transfers", headers=headers_with_transfer_idem, json=transfer_data)

            with lock:
                results.append({
                    "status_code": response.status_code,
                    "transfer_id": response.json().get("id") if response.status_code == 201 else None
                })
        except Exception as e:
            with lock:
                results.append({"error": str(e)})

    # Create threads
    thread1 = threading.Thread(target=make_transfer, args=(dest_acc1, 1))
    thread2 = threading.Thread(target=make_transfer, args=(dest_acc2, 2))

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    # Both should succeed
    assert len(results) == 2
    assert all(r.get("status_code") == 201 for r in results)

    # Should be different transfers
    transfer_ids = [r["transfer_id"] for r in results]
    assert len(set(transfer_ids)) == 2, "Concurrent transfers to different destinations should create different transfers"

    # Check final source balance
    source_after = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    assert source_after["balance"] == 50.0


def test_concurrent_same_idempotency_key_one_wins(authenticated_client):
    """
    Test concurrent requests with SAME idempotency key.
    One should execute, other should get cached response.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": source_acc["id"], "amount": 200.0, "description": "Initial deposit"}
    )

    idempotency_key = str(uuid.uuid4())
    headers_with_idempotency = {**headers, "Idempotency-Key": idempotency_key}

    transfer_data = {
        "source_account_id": source_acc["id"],
        "destination_account_id": dest_acc["id"],
        "amount": 100.0,
    }

    results = []
    lock = threading.Lock()

    def make_transfer():
        """Make transfer with same idempotency key."""
        try:
            response = client.post("/transfers", headers=headers_with_idempotency, json=transfer_data)

            with lock:
                results.append({
                    "status_code": response.status_code,
                    "transfer_id": response.json().get("id"),
                    "timestamp": time.time()
                })
        except Exception as e:
            with lock:
                results.append({"error": str(e)})

    # Create two threads sending concurrent requests
    thread1 = threading.Thread(target=make_transfer)
    thread2 = threading.Thread(target=make_transfer)

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    # Both should succeed
    assert len(results) == 2
    print(f"DEBUG - Same Idempotency Key Test: Results = {results}")  # Debug output
    assert all(r.get("status_code") == 201 for r in results), f"Expected 201 status codes, got: {[r.get('status_code') for r in results]}"

    # Both should return same transfer ID
    transfer_ids = [r["transfer_id"] for r in results]
    assert transfer_ids[0] == transfer_ids[1], "Concurrent requests with same idempotency key should return same transfer ID"

    # Balance should be deducted only once
    source_after = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    assert source_after["balance"] == 100.0, "Balance should be deducted only once despite concurrent requests"


def test_rapid_sequential_transfers(authenticated_client):
    """
    Test rapid sequential transfers to verify atomicity and balance tracking.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    # Deposit initial balance
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": source_acc["id"], "amount": 500.0, "description": "Initial deposit"}
    )

    # Create 5 destination accounts and transfer to each
    for i in range(5):
        dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

        transfer_data = {
            "source_account_id": source_acc["id"],
            "destination_account_id": dest_acc["id"],
            "amount": 50.0,
            "description": f"Transfer {i+1}"
        }
        headers_with_transfer_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
        response = client.post("/transfers", headers=headers_with_transfer_idem, json=transfer_data)
        assert response.status_code == 201, f"Transfer {i+1} failed"

    # Check final balance
    source_after = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    assert source_after["balance"] == 250.0, "Balance should decrease by 250 after 5 transfers of 50 each"


def test_concurrent_transfer_insufficient_funds(authenticated_client):
    """
    Test concurrent transfers when insufficient funds for both.
    One should succeed, one should fail.
    """
    client, headers, _ = authenticated_client

    source_acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    dest_acc1 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()
    dest_acc2 = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit only $150 (not enough for two $100 transfers)
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": source_acc["id"], "amount": 150.0, "description": "Limited deposit"}
    )

    results = []
    lock = threading.Lock()

    def make_transfer(dest_account):
        """Helper to make transfer in thread."""
        try:
            transfer_data = {
                "source_account_id": source_acc["id"],
                "destination_account_id": dest_account["id"],
                "amount": 100.0,
            }
            # Each transfer needs unique idempotency key
            headers_with_transfer_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
            response = client.post("/transfers", headers=headers_with_transfer_idem, json=transfer_data)

            with lock:
                results.append({"status_code": response.status_code})
        except Exception as e:
            with lock:
                results.append({"error": str(e)})

    thread1 = threading.Thread(target=make_transfer, args=(dest_acc1,))
    thread2 = threading.Thread(target=make_transfer, args=(dest_acc2,))

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    # One should succeed, one should fail
    assert len(results) == 2
    status_codes = [r.get("status_code") for r in results]

    assert 201 in status_codes, "One transfer should succeed"
    assert 400 in status_codes, "One transfer should fail with insufficient funds"

    # Verify account balance is correct
    source_after = client.get(f"/accounts/{source_acc['id']}", headers=headers).json()
    assert source_after["balance"] == 50.0, "Source balance should decrease by 100 (one successful transfer)"


def test_multiple_concurrent_requests_to_same_destination(authenticated_client):
    """
    Test multiple concurrent transfers from different sources to same destination.
    All should succeed and destination balance should be sum of all transfers.
    """
    client, headers, _ = authenticated_client

    # Create 3 source accounts
    source_accs = []
    for _ in range(3):
        acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
        source_accs.append(acc)
        # Deposit funds
        headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
        client.post(
            "/transactions/deposit",
            headers=headers_with_idem,
            json={"account_id": acc["id"], "amount": 100.0, "description": "Deposit"}
        )

    dest_acc = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    results = []
    lock = threading.Lock()

    def make_transfer(source_account):
        """Make transfer to shared destination."""
        try:
            transfer_data = {
                "source_account_id": source_account["id"],
                "destination_account_id": dest_acc["id"],
                "amount": 50.0,
            }
            # Each transfer needs unique idempotency key
            headers_with_transfer_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
            response = client.post("/transfers", headers=headers_with_transfer_idem, json=transfer_data)

            with lock:
                results.append({"status_code": response.status_code})
        except Exception as e:
            with lock:
                results.append({"error": str(e)})

    # Create and start threads
    threads = [threading.Thread(target=make_transfer, args=(acc,)) for acc in source_accs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All should succeed
    assert len(results) == 3
    assert all(r.get("status_code") == 201 for r in results), "All concurrent transfers should succeed"

    # Check destination balance
    dest_after = client.get(f"/accounts/{dest_acc['id']}", headers=headers).json()
    assert dest_after["balance"] == 150.0, f"Destination balance should be 150.0, got {dest_after['balance']}"


def test_circular_concurrent_transfers(authenticated_client):
    """
    Test circular transfers: Account A sends to Account B while Account B sends to Account A.
    This tests deadlock prevention via deterministic account locking order.

    The scenario:
    - Thread 1: A -> B with $50
    - Thread 2: B -> A with $30
    Both should succeed without deadlock, even though they lock accounts in opposite logical order.
    """
    client, headers, _ = authenticated_client

    # Create two accounts with initial balances
    acc_a = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    acc_b = client.post("/accounts", headers=headers, json={"type": "SAVINGS"}).json()

    # Deposit initial balances
    headers_with_idem_a = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem_a,
        json={"account_id": acc_a["id"], "amount": 100.0, "description": "Initial balance A"}
    )

    headers_with_idem_b = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem_b,
        json={"account_id": acc_b["id"], "amount": 100.0, "description": "Initial balance B"}
    )

    results = []
    lock = threading.Lock()

    def transfer_a_to_b():
        """Transfer from A to B."""
        try:
            transfer_data = {
                "source_account_id": acc_a["id"],
                "destination_account_id": acc_b["id"],
                "amount": 50.0,
            }
            headers_with_transfer_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
            response = client.post("/transfers", headers=headers_with_transfer_idem, json=transfer_data)

            with lock:
                results.append({
                    "direction": "A->B",
                    "status_code": response.status_code
                })
        except Exception as e:
            with lock:
                results.append({"direction": "A->B", "error": str(e)})

    def transfer_b_to_a():
        """Transfer from B to A."""
        try:
            transfer_data = {
                "source_account_id": acc_b["id"],
                "destination_account_id": acc_a["id"],
                "amount": 30.0,
            }
            headers_with_transfer_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
            response = client.post("/transfers", headers=headers_with_transfer_idem, json=transfer_data)

            with lock:
                results.append({
                    "direction": "B->A",
                    "status_code": response.status_code
                })
        except Exception as e:
            with lock:
                results.append({"direction": "B->A", "error": str(e)})

    # Start both transfers simultaneously
    thread1 = threading.Thread(target=transfer_a_to_b)
    thread2 = threading.Thread(target=transfer_b_to_a)

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    # Both should succeed
    assert len(results) == 2, "Both transfers should complete"
    assert all(r.get("status_code") == 201 for r in results), "Both transfers should succeed (no deadlock)"

    # Verify final balances
    # A: started with 100, sent 50, received 30 = 80
    # B: started with 100, received 50, sent 30 = 120
    acc_a_final = client.get(f"/accounts/{acc_a['id']}", headers=headers).json()
    acc_b_final = client.get(f"/accounts/{acc_b['id']}", headers=headers).json()

    assert acc_a_final["balance"] == 80.0, f"Account A should have 80.0, got {acc_a_final['balance']}"
    assert acc_b_final["balance"] == 120.0, f"Account B should have 120.0, got {acc_b_final['balance']}"
