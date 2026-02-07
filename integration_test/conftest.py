import os
import sys


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
    
    # test client
    with TestClient(app) as test_client:
        yield test_client

    # clear overrides
    app.dependency_overrides.clear()
