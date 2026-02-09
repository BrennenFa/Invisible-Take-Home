#!/usr/bin/env python3
"""
Banking API Test Client

Demonstrates the complete transfer workflow between two users.
Run the server first: uvicorn app.main:app --reload
"""

import requests
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000"


def print_step(step: int, description: str):
    print(f"\n{'='*60}")
    print(f"Step {step}: {description}")
    print('='*60)


def print_response(response: requests.Response):
    print(f"Status: {response.status_code}")
    try:
        print(f"Response: {response.json()}")
    except:
        print(f"Response: {response.text}")


def main():
    print("\nBanking API Test Client")
    print("=" * 60)

    # Step 1: Register User A (Alice - Sender)
    print_step(1, "Register User A (Alice - Sender)")
    response = requests.post(
        f"{BASE_URL}/auth/signup",
        json={"email": f"alice_{uuid.uuid4().hex[:8]}@example.com", "password": "SecurePass123"}
    )
    print_response(response)
    if response.status_code != 200:
        print("Failed to register Alice")
        sys.exit(1)
    alice_token = response.json()["access_token"]
    print(f"Alice's token acquired")

    # Step 2: Register User B (Bob - Recipient)
    print_step(2, "Register User B (Bob - Recipient)")
    response = requests.post(
        f"{BASE_URL}/auth/signup",
        json={"email": f"bob_{uuid.uuid4().hex[:8]}@example.com", "password": "SecurePass456"}
    )
    print_response(response)
    if response.status_code != 200:
        print("Failed to register Bob")
        sys.exit(1)
    bob_token = response.json()["access_token"]
    print(f"Bob's token acquired")

    # Step 3: Bob creates an account
    print_step(3, "Bob creates a CHECKING account")
    response = requests.post(
        f"{BASE_URL}/accounts",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={"type": "CHECKING"}
    )
    print_response(response)
    if response.status_code not in (200, 201):
        print("Failed to create Bob's account")
        sys.exit(1)
    bob_account = response.json()
    bob_account_number = bob_account["account_number"]
    bob_routing_number = bob_account["routing_number"]
    print(f"Bob's account number: {bob_account_number}")
    print(f"Bob's routing number: {bob_routing_number}")

    # Step 4: Alice creates an account
    print_step(4, "Alice creates a CHECKING account")
    response = requests.post(
        f"{BASE_URL}/accounts",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"type": "CHECKING"}
    )
    print_response(response)
    if response.status_code not in (200, 201):
        print("Failed to create Alice's account")
        sys.exit(1)
    alice_account = response.json()
    alice_account_id = alice_account["id"]
    print(f"Alice's account ID: {alice_account_id}")

    # Step 5: Alice deposits funds
    print_step(5, "Alice deposits $1000")
    idempotency_key = str(uuid.uuid4())
    response = requests.post(
        f"{BASE_URL}/transactions/deposit",
        headers={
            "Authorization": f"Bearer {alice_token}",
            "Idempotency-Key": idempotency_key
        },
        json={"account_id": alice_account_id, "amount": 1000.00}
    )
    print_response(response)
    if response.status_code not in (200, 201):
        print("Failed to deposit funds")
        sys.exit(1)

    # Step 6: Check Alice's balance
    print_step(6, "Check Alice's balance after deposit")
    response = requests.get(
        f"{BASE_URL}/accounts/{alice_account_id}",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    print_response(response)
    print(f"Alice's balance: ${response.json()['balance']}")

    # Step 7: Alice transfers to Bob using account number
    print_step(7, "Alice transfers $250 to Bob")
    transfer_key = str(uuid.uuid4())
    response = requests.post(
        f"{BASE_URL}/transfers/account",
        headers={
            "Authorization": f"Bearer {alice_token}",
            "Idempotency-Key": transfer_key
        },
        json={
            "source_account_id": alice_account_id,
            "destination_account_number": bob_account_number,
            "destination_routing_number": bob_routing_number,
            "amount": 250.00,
            "description": "Rent payment"
        }
    )
    print_response(response)
    if response.status_code not in (200, 201):
        print("Failed to transfer funds")
        sys.exit(1)

    # Step 8: Check final balances
    print_step(8, "Check final balances")

    # Alice's balance
    response = requests.get(
        f"{BASE_URL}/accounts/{alice_account_id}",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    alice_balance = response.json()["balance"]
    print(f"Alice's final balance: ${alice_balance}")

    # Bob's balance
    response = requests.get(
        f"{BASE_URL}/accounts/{bob_account['id']}",
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    bob_balance = response.json()["balance"]
    print(f"Bob's final balance: ${bob_balance}")

    # Step 9: Get Alice's transaction history
    print_step(9, "Alice's transaction history")
    response = requests.get(
        f"{BASE_URL}/accounts/{alice_account_id}/transactions",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    transactions = response.json()
    for txn in transactions:
        print(f"  {txn['type']}: ${txn['amount']} - {txn.get('description', 'N/A')}")

    # Step 10: Generate statement for Alice
    print_step(10, "Generate Alice's account statement (JSON)")
    response = requests.get(
        f"{BASE_URL}/statements/account/{alice_account_id}?format=json",
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    print_response(response)

    # Summary
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"Alice: Started with $0 -> Deposited $1000 -> Sent $250 -> Final: ${alice_balance}")
    print(f"Bob:   Started with $0 -> Received $250 -> Final: ${bob_balance}")

    if alice_balance == 750.0 and bob_balance == 250.0:
        print("\nAll assertions passed!")
        return 0
    else:
        print("\nBalance mismatch detected!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
