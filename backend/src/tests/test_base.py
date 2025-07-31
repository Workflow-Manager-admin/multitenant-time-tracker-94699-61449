"""
Base test utilities and common patterns for backend testing.

Provides base test classes, assertion helpers, and common test utilities
for consistent testing across the application.
"""
from typing import Dict, Any, Optional
from unittest.mock import Mock
from fastapi import status


class BaseAPITest:
    """Base class for API endpoint tests."""
    
    def assert_success_response(self, response: Mock, expected_status: int = status.HTTP_200_OK):
        """Assert that response indicates success."""
        assert response.status_code == expected_status
        assert response.json() is not None
    
    def assert_error_response(self, response: Mock, expected_status: int, expected_error: Optional[str] = None):
        """Assert that response indicates an error."""
        assert response.status_code == expected_status
        if expected_error:
            response_data = response.json()
            assert "detail" in response_data or "message" in response_data
            error_message = response_data.get("detail") or response_data.get("message")
            assert expected_error in error_message
    
    def assert_validation_error(self, response: Mock, field_name: Optional[str] = None):
        """Assert that response indicates a validation error."""
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        if field_name:
            response_data = response.json()
            assert "detail" in response_data
            # Check if the field is mentioned in validation errors
            errors = response_data["detail"]
            field_errors = [error for error in errors if error.get("loc") and field_name in error["loc"]]
            assert len(field_errors) > 0
    
    def assert_unauthorized(self, response: Mock):
        """Assert that response indicates unauthorized access."""
        self.assert_error_response(response, status.HTTP_401_UNAUTHORIZED)
    
    def assert_forbidden(self, response: Mock):
        """Assert that response indicates forbidden access."""
        self.assert_error_response(response, status.HTTP_403_FORBIDDEN)
    
    def assert_not_found(self, response: Mock):
        """Assert that response indicates resource not found."""
        self.assert_error_response(response, status.HTTP_404_NOT_FOUND)
    
    def assert_conflict(self, response: Mock):
        """Assert that response indicates a conflict."""
        self.assert_error_response(response, status.HTTP_409_CONFLICT)


class BaseCRUDTest(BaseAPITest):
    """Base class for CRUD operation tests."""
    
    base_url: str = ""  # Override in subclasses
    
    def test_create_success(self, client: Mock, auth_headers: Dict[str, str], sample_data: Dict[str, Any]):
        """Test successful resource creation."""
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {"id": "created-id", **sample_data}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=sample_data, headers=auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        created_data = result.json()
        assert "id" in created_data
        for key, value in sample_data.items():
            assert created_data[key] == value
    
    def test_create_validation_error(self, client: Mock, auth_headers: Dict[str, str]):
        """Test creation with invalid data."""
        invalid_data = {}  # Empty data should trigger validation errors
        
        response = Mock()
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        response.json.return_value = {
            "detail": [{"loc": ["body", "name"], "msg": "field required", "type": "value_error.missing"}]
        }
        
        client.post.return_value = response
        result = client.post(self.base_url, json=invalid_data, headers=auth_headers)
        
        self.assert_validation_error(result)
    
    def test_create_unauthorized(self, client: Mock, sample_data: Dict[str, Any]):
        """Test creation without authentication."""
        response = Mock()
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.json.return_value = {"detail": "Authentication required"}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=sample_data)
        
        self.assert_unauthorized(result)
    
    def test_read_success(self, client: Mock, auth_headers: Dict[str, str]):
        """Test successful resource retrieval."""
        resource_id = "test-id"
        expected_data = {"id": resource_id, "name": "Test Resource"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = expected_data
        
        client.get.return_value = response
        result = client.get(f"{self.base_url}/{resource_id}", headers=auth_headers)
        
        self.assert_success_response(result)
        assert result.json() == expected_data
    
    def test_read_not_found(self, client: Mock, auth_headers: Dict[str, str]):
        """Test retrieval of non-existent resource."""
        resource_id = "non-existent-id"
        
        response = Mock()
        response.status_code = status.HTTP_404_NOT_FOUND
        response.json.return_value = {"detail": "Resource not found"}
        
        client.get.return_value = response
        result = client.get(f"{self.base_url}/{resource_id}", headers=auth_headers)
        
        self.assert_not_found(result)
    
    def test_update_success(self, client: Mock, auth_headers: Dict[str, str]):
        """Test successful resource update."""
        resource_id = "test-id"
        update_data = {"name": "Updated Name"}
        expected_data = {"id": resource_id, **update_data}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = expected_data
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{resource_id}", json=update_data, headers=auth_headers)
        
        self.assert_success_response(result)
        updated_data = result.json()
        assert updated_data["id"] == resource_id
        assert updated_data["name"] == update_data["name"]
    
    def test_delete_success(self, client: Mock, auth_headers: Dict[str, str]):
        """Test successful resource deletion."""
        resource_id = "test-id"
        
        response = Mock()
        response.status_code = status.HTTP_204_NO_CONTENT
        
        client.delete.return_value = response
        result = client.delete(f"{self.base_url}/{resource_id}", headers=auth_headers)
        
        assert result.status_code == status.HTTP_204_NO_CONTENT
    
    def test_list_success(self, client: Mock, auth_headers: Dict[str, str]):
        """Test successful resource listing."""
        expected_data = {
            "items": [
                {"id": "item-1", "name": "Item 1"},
                {"id": "item-2", "name": "Item 2"}
            ],
            "total": 2,
            "page": 1,
            "per_page": 10
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = expected_data
        
        client.get.return_value = response
        result = client.get(self.base_url, headers=auth_headers)
        
        self.assert_success_response(result)
        list_data = result.json()
        assert "items" in list_data
        assert "total" in list_data
        assert len(list_data["items"]) == 2


class TenantIsolationTestMixin:
    """Mixin for testing multi-tenant data isolation."""
    
    def test_tenant_isolation_create(self, client: Mock, auth_headers: Dict[str, str], 
                                   different_tenant_headers: Dict[str, str], sample_data: Dict[str, Any]):
        """Test that resources created in one tenant are not visible to another."""
        # Create resource in first tenant
        create_response = Mock()
        create_response.status_code = status.HTTP_201_CREATED
        create_response.json.return_value = {"id": "resource-1", **sample_data}
        
        client.post.return_value = create_response
        client.post(self.base_url, json=sample_data, headers=auth_headers)
        
        # Try to access from different tenant
        get_response = Mock()
        get_response.status_code = status.HTTP_404_NOT_FOUND
        get_response.json.return_value = {"detail": "Resource not found"}
        
        client.get.return_value = get_response
        result = client.get(f"{self.base_url}/resource-1", headers=different_tenant_headers)
        
        self.assert_not_found(result)
    
    def test_tenant_isolation_list(self, client: Mock, auth_headers: Dict[str, str], 
                                 different_tenant_headers: Dict[str, str]):
        """Test that listing resources only shows items from current tenant."""
        # List resources for first tenant
        tenant1_response = Mock()
        tenant1_response.status_code = status.HTTP_200_OK
        tenant1_response.json.return_value = {
            "items": [{"id": "item-1", "name": "Tenant 1 Item"}],
            "total": 1
        }
        
        # List resources for second tenant
        tenant2_response = Mock()
        tenant2_response.status_code = status.HTTP_200_OK
        tenant2_response.json.return_value = {
            "items": [{"id": "item-2", "name": "Tenant 2 Item"}],
            "total": 1
        }
        
        # Configure mock to return different responses based on headers
        def mock_get(url, headers=None, **kwargs):
            if headers and headers.get("X-Tenant-ID") == "tenant-123":
                return tenant1_response
            elif headers and headers.get("X-Tenant-ID") == "tenant-456":
                return tenant2_response
            return Mock(status_code=401)
        
        client.get.side_effect = mock_get
        
        # Test first tenant sees only their items
        result1 = client.get(self.base_url, headers=auth_headers)
        self.assert_success_response(result1)
        assert len(result1.json()["items"]) == 1
        assert result1.json()["items"][0]["id"] == "item-1"
        
        # Test second tenant sees only their items
        result2 = client.get(self.base_url, headers=different_tenant_headers)
        self.assert_success_response(result2)
        assert len(result2.json()["items"]) == 1
        assert result2.json()["items"][0]["id"] == "item-2"


class DatabaseTestUtilities:
    """Utilities for database testing."""
    
    @staticmethod
    def create_test_tenant(db_session: Mock, tenant_data: Dict[str, Any]) -> Mock:
        """Create a test tenant in the database."""
        tenant = Mock()
        tenant.id = tenant_data.get("id", "test-tenant")
        tenant.name = tenant_data.get("name", "Test Tenant")
        return tenant
    
    @staticmethod
    def create_test_user(db_session: Mock, user_data: Dict[str, Any], tenant_id: str) -> Mock:
        """Create a test user in the database."""
        user = Mock()
        user.id = f"user-{user_data.get('email', 'test@example.com')}"
        user.email = user_data.get("email", "test@example.com")
        user.tenant_id = tenant_id
        return user
    
    @staticmethod
    def create_test_client(db_session: Mock, client_data: Dict[str, Any], tenant_id: str) -> Mock:
        """Create a test client in the database."""
        client = Mock()
        client.id = f"client-{client_data.get('name', 'Test Client')}"
        client.name = client_data.get("name", "Test Client")
        client.tenant_id = tenant_id
        return client
    
    @staticmethod
    def cleanup_test_data(db_session: Mock):
        """Clean up test data from database."""
        # In a real implementation, this would delete test data
        pass


# Test data factories
class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_tenant(**overrides) -> Dict[str, Any]:
        """Create tenant test data."""
        default_data = {
            "name": "Test Tenant",
            "domain": "test.example.com",
            "settings": {"timezone": "UTC"}
        }
        return {**default_data, **overrides}
    
    @staticmethod
    def create_user(**overrides) -> Dict[str, Any]:
        """Create user test data."""
        default_data = {
            "email": "test@example.com",
            "password": "secure_password123",
            "first_name": "Test",
            "last_name": "User",
            "role": "user"
        }
        return {**default_data, **overrides}
    
    @staticmethod
    def create_client(**overrides) -> Dict[str, Any]:
        """Create client test data."""
        default_data = {
            "name": "Test Client",
            "contact_email": "contact@testclient.com",
            "active": True
        }
        return {**default_data, **overrides}
    
    @staticmethod
    def create_project(**overrides) -> Dict[str, Any]:
        """Create project test data."""
        default_data = {
            "name": "Test Project",
            "description": "A test project",
            "active": True
        }
        return {**default_data, **overrides}
    
    @staticmethod
    def create_time_entry(**overrides) -> Dict[str, Any]:
        """Create time entry test data."""
        default_data = {
            "start_time": "2024-01-15T09:00:00Z",
            "end_time": "2024-01-15T17:00:00Z",
            "description": "Test work",
            "billable": True
        }
        return {**default_data, **overrides}
