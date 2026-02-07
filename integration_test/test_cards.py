import pytest
import uuid

# ========== AUTHENTICATED TESTS ==========

def test_create_card_success(authenticated_client):
    """Test successful card creation for a valid account."""
    client, headers, _ = authenticated_client

    # create an account
    acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    # create a card
    card_data = {
        "account_id": acc["id"],
        "card_type": "DEBIT",
        "card_holder_name": "John Doe",
        "pin": "1234",
        "spending_limit": 1000.0
    }
    
    response = client.post("/cards", headers=headers, json=card_data)
    assert response.status_code == 201
    

    # validate card existance
    data = response.json()
    assert data["card_holder_name"] == "John Doe"
    assert len(data["card_number"]) == 16
    assert data["status"] == "ACTIVE"


def test_create_card_invalid_pin(authenticated_client):
    """Test card creation fails with non-4-digit PIN."""
    client, headers, _ = authenticated_client
    acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()

    # card data with invalid pin
    card_data = {
        "account_id": acc["id"],
        "card_type": "DEBIT",
        "card_holder_name": "John Doe",
        "pin": "12a",
        "spending_limit": 1000.0
    }
    
    response = client.post("/cards", headers=headers, json=card_data)
    assert response.status_code == 400
    assert "PIN must be exactly 4 digits" in response.json()["detail"]


def test_get_cards_list(authenticated_client):
    """Test retrieving all cards for the user."""
    client, headers, _ = authenticated_client
    
    # Create an account and a card
    acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    client.post("/cards", headers=headers, json={
        "account_id": acc["id"], "card_type": "DEBIT", 
        "card_holder_name": "Test User", "pin": "1111"
    })

    response = client.get("/cards", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_freeze_and_unfreeze_card(authenticated_client):
    """Test the card lifecycle: Active -> Frozen -> Active."""
    client, headers, _ = authenticated_client
    
    # Create card
    acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    card = client.post("/cards", headers=headers, json={
        "account_id": acc["id"], "card_type": "DEBIT", 
        "card_holder_name": "Test User", "pin": "1111"
    }).json()

    # Freeze
    freeze_res = client.patch(f"/cards/{card['id']}/freeze", headers=headers)
    assert freeze_res.status_code == 200
    assert freeze_res.json()["status"] == "FROZEN"

    # Unfreeze
    unfreeze_res = client.patch(f"/cards/{card['id']}/unfreeze", headers=headers)
    assert unfreeze_res.status_code == 200
    assert unfreeze_res.json()["status"] == "ACTIVE"


def test_cancel_card_permanent(authenticated_client):
    """Test that a cancelled card cannot be frozen or unfrozen."""
    client, headers, _ = authenticated_client
    
    acc = client.post("/accounts", headers=headers, json={"type": "CHECKING"}).json()
    card = client.post("/cards", headers=headers, json={
        "account_id": acc["id"], "card_type": "DEBIT", 
        "card_holder_name": "Test User", "pin": "1111"
    }).json()

    # Cancel
    client.delete(f"/cards/{card['id']}", headers=headers)
    
    # Try to freeze
    response = client.patch(f"/cards/{card['id']}/freeze", headers=headers)
    assert response.status_code == 400
    assert "cancelled" in response.json()["detail"].lower()


# ========== UNAUTHENTICATED TESTS ==========

def test_get_cards_unauthenticated(client):
    response = client.get("/cards")
    assert response.status_code == 401


def test_card_action_unauthenticated(client):
    fake_id = str(uuid.uuid4())
    response = client.patch(f"/cards/{fake_id}/freeze")
    assert response.status_code == 401