import pytest
import uuid


@pytest.fixture
def user_data():
    """Generates a unique email and password for each test run."""
    random_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test_{random_id}@gmail.com",
        "password": "password2"
    }

def test_auth_workflow(client, user_data):
    """
    Tests the full authentication flow:
    1. Signup
    2. Login (retrieve token)
    3. Get 'Me' endpoint (verify token works)
    """
    
    # Sign up
    signup_response = client.post("/auth/signup", json=user_data)
    
    assert signup_response.status_code in [200, 201], \
        f"Signup failed: {signup_response.text}"

    # Login
    login_response = client.post("/auth/login", json=user_data)
    
    assert login_response.status_code == 200, \
        f"Login failed: {login_response.text}"
    
    login_json = login_response.json()
    
    assert "access_token" in login_json, "Response did not contain 'access_token'"
    token = login_json["access_token"]
    
    # Validate login with get me route
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    me_response = client.get("/auth/me", headers=headers)
    
    assert me_response.status_code == 200, \
        f"Get Me failed: {me_response.text}"
    
    # Verify the data returned matches the user we created
    me_json = me_response.json()
    assert me_json["email"] == user_data["email"]