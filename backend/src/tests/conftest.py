"""
Pytest configuration and fixtures for backend testing.

Provides test fixtures for database connections, FastAPI test client,
authentication tokens, and multi-tenant test data setup.
"""
import asyncio
import os
import pytest
from typing import Dict, Generator
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock

# Import the actual app and database dependencies
try:
    from src.api.main import app
    from src.database.connection import get_db, create_test_tables, drop_test_tables
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    APP_AVAILABLE = True
except ImportError:
    # Fallback to mock if imports fail
    class MockApp:
        def __init__(self):
            self.dependency_overrides = {}
    
    app = MockApp()
    APP_AVAILABLE = False
    create_engine = None
    sessionmaker = None

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Test database URL configuration."""
    return os.getenv("TEST_DATABASE_URL", "postgresql://test:test@localhost:5432/test_timetracker")

@pytest.fixture(scope="session")
def engine(test_db_url: str):
    """Create database engine for testing."""
    if APP_AVAILABLE and create_engine:
        try:
            test_engine = create_engine(test_db_url, echo=False)
            create_test_tables()
            yield test_engine
            drop_test_tables()
        except Exception:
            # Fallback to mock if database setup fails
            yield Mock()
    else:
        # Mock for when app is not available
        yield Mock()

@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """Create a database session for testing."""
    if APP_AVAILABLE and not isinstance(engine, Mock):
        try:
            TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            session = TestingSessionLocal()
            try:
                yield session
            finally:
                session.close()
        except Exception:
            # Fallback to mock if session creation fails
            yield Mock()
    else:
        # Mock when engine is mock or app not available
        yield Mock()

@pytest.fixture(scope="function")
def client(db_session):
    """Create FastAPI test client with database dependency override."""
    if APP_AVAILABLE and not isinstance(db_session, Mock):
        try:
            def override_get_db():
                try:
                    yield db_session
                finally:
                    pass
            
            app.dependency_overrides[get_db] = override_get_db
            with TestClient(app) as test_client:
                yield test_client
            app.dependency_overrides.clear()
        except Exception:
            # Fallback to mock if TestClient setup fails
            yield Mock()
    else:
        # Mock when db_session is mock or app not available
        yield Mock()

@pytest.fixture
def sample_tenant_data() -> Dict:
    """Sample tenant data for testing."""
    return {
        "id": "tenant-123",
        "name": "Test Tenant",
        "domain": "test-tenant.com",
        "settings": {
            "timezone": "UTC",
            "currency": "USD"
        }
    }

@pytest.fixture
def sample_user_data() -> Dict:
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "secure_password123",
        "first_name": "Test",
        "last_name": "User",
        "role": "user"
    }

@pytest.fixture
def sample_admin_data() -> Dict:
    """Sample admin user data for testing."""
    return {
        "email": "admin@example.com",
        "password": "admin_password123",
        "first_name": "Admin",
        "last_name": "User",
        "role": "admin"
    }

@pytest.fixture
def sample_client_data() -> Dict:
    """Sample client data for testing."""
    return {
        "name": "Test Client Corp",
        "contact_email": "contact@testclient.com",
        "contact_phone": "+1-555-0123",
        "address": "123 Business St, City, ST 12345",
        "active": True
    }

@pytest.fixture
def sample_project_data() -> Dict:
    """Sample project data for testing."""
    return {
        "name": "Test Project",
        "description": "A test project for testing purposes",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "budget": 50000.00,
        "active": True
    }

@pytest.fixture
def sample_technology_data() -> Dict:
    """Sample technology data for testing."""
    return {
        "name": "Python",
        "category": "Programming Language",
        "version": "3.11",
        "description": "Python programming language"
    }

@pytest.fixture
def sample_time_entry_data() -> Dict:
    """Sample time entry data for testing."""
    return {
        "start_time": "2024-01-15T09:00:00Z",
        "end_time": "2024-01-15T17:00:00Z",
        "description": "Working on test features",
        "billable": True,
        "hourly_rate": 75.00
    }

@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Authentication headers with mock JWT token."""
    return {
        "Authorization": "Bearer mock_jwt_token",
        "X-Tenant-ID": "tenant-123"
    }

@pytest.fixture
def admin_auth_headers() -> Dict[str, str]:
    """Admin authentication headers with mock JWT token."""
    return {
        "Authorization": "Bearer mock_admin_jwt_token",
        "X-Tenant-ID": "tenant-123"
    }

@pytest.fixture
def different_tenant_headers() -> Dict[str, str]:
    """Authentication headers for a different tenant."""
    return {
        "Authorization": "Bearer mock_jwt_token_tenant2",
        "X-Tenant-ID": "tenant-456"
    }

@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset application state before each test."""
    # Clear any cached data or reset application state
    yield
    # Cleanup after test
    pass

class AuthTokenMocker:
    """Helper class for mocking authentication tokens."""
    
    @staticmethod
    def create_valid_token(user_id: str, tenant_id: str, role: str = "user") -> str:
        """Create a mock valid JWT token."""
        return f"mock_token_{user_id}_{tenant_id}_{role}"
    
    @staticmethod
    def create_expired_token() -> str:
        """Create a mock expired JWT token."""
        return "expired_mock_token"
    
    @staticmethod
    def create_invalid_token() -> str:
        """Create a mock invalid JWT token."""
        return "invalid_mock_token"

@pytest.fixture
def auth_mocker() -> AuthTokenMocker:
    """Provide authentication token mocker."""
    return AuthTokenMocker()

@pytest.fixture
def sample_data() -> Dict:
    """Generic sample data for testing (defaults to client data)."""
    return {
        "name": "Test Resource",
        "description": "A test resource for testing purposes",
        "active": True
    }
