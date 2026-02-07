import os
import sys
import uuid


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# allow for import to app

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import Base, get_db
from dotenv import load_dotenv

load_dotenv()

# In-memory database for test isolation
DB_URL = "sqlite:///:memory:"


engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    # Create tables
    Base.metadata.create_all(bind=engine)


    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # drop tables
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client that uses the override_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    # db override
    app.dependency_overrides[get_db] = override_get_db

    # Disable rate limiting for tests
    app.state.limiter.enabled = False

    # test client
    with TestClient(app) as test_client:
        yield test_client

    # clear overrides
    app.dependency_overrides.clear()
    app.state.limiter.enabled = True


@pytest.fixture
def user_data():
    """Generates a unique email and password for each test run."""
    random_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test_{random_id}@gmail.com",
        "password": "password2"
    }


@pytest.fixture
def authenticated_client(client, user_data):
    """
    Returns a tuple of (client, headers, user_data) with a valid auth token.
    Handles signup and login automatically for tests that need authentication.
    Can be used across all test files.
    """
    # Sign up
    signup_response = client.post("/auth/signup", json=user_data)
    assert signup_response.status_code in [200, 201], \
        f"Signup failed during fixture setup: {signup_response.text}"

    # Login
    login_response = client.post("/auth/login", json=user_data)
    assert login_response.status_code == 200, \
        f"Login failed during fixture setup: {login_response.text}"

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    return client, headers, user_data
