import pytest
import uuid
from datetime import datetime, timedelta


def test_statement_json_format(authenticated_client):
    """Test generating statement in JSON format."""
    client, headers, user_data = authenticated_client

    # Create account and add transactions
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    # Add some transactions
    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 100.0}
    )

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/withdrawal",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 25.0}
    )

    # Generate statement
    now = datetime.utcnow()
    start_date = (now - timedelta(days=1)).isoformat()
    end_date = (now + timedelta(days=1)).isoformat()

    response = client.get(
        f"/statements/account/{account_id}?start_date={start_date}&end_date={end_date}&format=json",
        headers=headers
    )

    assert response.status_code == 200, f"Statement generation failed: {response.text}"
    statement = response.json()
    assert "account_id" in statement
    assert "transactions" in statement
    assert len(statement["transactions"]) == 2
    assert "opening_balance" in statement
    assert "closing_balance" in statement


def test_statement_csv_format(authenticated_client):
    """Test generating statement in CSV format."""
    client, headers, user_data = authenticated_client

    # Create account and add transaction
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 100.0}
    )

    # Generate CSV statement
    now = datetime.utcnow()
    start_date = (now - timedelta(days=1)).isoformat()
    end_date = (now + timedelta(days=1)).isoformat()

    response = client.get(
        f"/statements/account/{account_id}?start_date={start_date}&end_date={end_date}&format=csv",
        headers=headers
    )

    assert response.status_code == 200, f"CSV generation failed: {response.text}"
    assert "text/csv" in response.headers.get("content-type", "")
    assert len(response.text) > 0


def test_statement_pdf_format(authenticated_client):
    """Test generating statement in PDF format."""
    client, headers, user_data = authenticated_client

    # Create account and add transaction
    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    headers_with_idem = {**headers, "Idempotency-Key": str(uuid.uuid4())}
    client.post(
        "/transactions/deposit",
        headers=headers_with_idem,
        json={"account_id": account_id, "amount": 100.0}
    )

    # Generate PDF statement
    now = datetime.utcnow()
    start_date = (now - timedelta(days=1)).isoformat()
    end_date = (now + timedelta(days=1)).isoformat()

    response = client.get(
        f"/statements/account/{account_id}?start_date={start_date}&end_date={end_date}&format=pdf",
        headers=headers
    )

    assert response.status_code == 200, f"PDF generation failed: {response.text}"
    assert "application/pdf" in response.headers.get("content-type", "")
    assert len(response.content) > 0


def test_statement_invalid_date_range(authenticated_client):
    """Test statement fails with invalid date range."""
    client, headers, user_data = authenticated_client

    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    # start_date >= end_date
    now = datetime.utcnow()
    start_date = (now + timedelta(days=1)).isoformat()
    end_date = (now - timedelta(days=1)).isoformat()

    response = client.get(
        f"/statements/account/{account_id}?start_date={start_date}&end_date={end_date}&format=json",
        headers=headers
    )

    assert response.status_code == 400, f"Expected 400: {response.text}"
    assert "Start date must be before end date" in response.json()["detail"]


def test_statement_nonexistent_account(authenticated_client):
    """Test statement fails for nonexistent account."""
    client, headers, user_data = authenticated_client

    fake_account_id = str(uuid.uuid4())
    now = datetime.utcnow()
    start_date = (now - timedelta(days=1)).isoformat()
    end_date = (now + timedelta(days=1)).isoformat()

    response = client.get(
        f"/statements/account/{fake_account_id}?start_date={start_date}&end_date={end_date}&format=json",
        headers=headers
    )

    assert response.status_code == 404, f"Expected 404: {response.text}"


def test_statement_unauthenticated(client):
    """Test statement fails without authentication."""
    account_id = str(uuid.uuid4())
    now = datetime.utcnow()
    start_date = (now - timedelta(days=1)).isoformat()
    end_date = (now + timedelta(days=1)).isoformat()

    response = client.get(
        f"/statements/account/{account_id}?start_date={start_date}&end_date={end_date}&format=json"
    )

    assert response.status_code == 401, f"Expected 401: {response.text}"


def test_statement_empty_date_range(authenticated_client):
    """Test statement with no transactions in date range."""
    client, headers, user_data = authenticated_client

    acc_response = client.post("/accounts", headers=headers, json={"type": "CHECKING"})
    account_id = acc_response.json()["id"]

    # Query with dates before any transactions
    now = datetime.utcnow()
    start_date = (now - timedelta(days=10)).isoformat()
    end_date = (now - timedelta(days=5)).isoformat()

    response = client.get(
        f"/statements/account/{account_id}?start_date={start_date}&end_date={end_date}&format=json",
        headers=headers
    )

    assert response.status_code == 200, f"Statement generation failed: {response.text}"
    statement = response.json()
    assert len(statement["transactions"]) == 0
