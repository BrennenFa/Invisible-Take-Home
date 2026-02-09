import pytest


def test_health_check(client):
    """Test that the health check endpoint returns OK status."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"


def test_health_check_method_not_allowed(client):
    """Test that POST to health check is not allowed."""
    response = client.post("/")
    assert response.status_code == 405
