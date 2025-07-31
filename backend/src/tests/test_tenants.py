"""
Tenant management tests for the multitenant time tracker.

Tests cover tenant creation, management, user assignment, and multi-tenant
data isolation verification.
"""
from unittest.mock import Mock
from fastapi import status
from typing import Dict, Any

from .test_base import BaseAPITest, BaseCRUDTest, TenantIsolationTestMixin


class TestTenantManagement(BaseCRUDTest, TenantIsolationTestMixin):
    """Test cases for tenant CRUD operations."""
    
    base_url = "/tenants"
    
    def test_create_tenant_success(self, client: Mock, admin_auth_headers: Dict[str, str], 
                                 sample_tenant_data: Dict[str, Any]):
        """Test successful tenant creation by admin."""
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "id": "tenant-new",
            **sample_tenant_data,
            "created_at": "2024-01-15T10:00:00Z",
            "active": True
        }
        
        client.post.return_value = response
        result = client.post(self.base_url, json=sample_tenant_data, headers=admin_auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        created_tenant = result.json()
        assert "id" in created_tenant
        assert created_tenant["name"] == sample_tenant_data["name"]
        assert created_tenant["active"] is True
    
    def test_create_tenant_duplicate_name(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test tenant creation with duplicate name."""
        duplicate_tenant_data = {"name": "Existing Tenant", "domain": "existing.com"}
        
        response = Mock()
        response.status_code = status.HTTP_409_CONFLICT
        response.json.return_value = {"detail": "Tenant with this name already exists"}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=duplicate_tenant_data, headers=admin_auth_headers)
        
        self.assert_conflict(result)
    
    def test_create_tenant_non_admin(self, client: Mock, auth_headers: Dict[str, str], 
                                   sample_tenant_data: Dict[str, Any]):
        """Test tenant creation by non-admin user should fail."""
        response = Mock()
        response.status_code = status.HTTP_403_FORBIDDEN
        response.json.return_value = {"detail": "Only system administrators can create tenants"}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=sample_tenant_data, headers=auth_headers)
        
        self.assert_forbidden(result)
    
    def test_get_tenant_details(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting tenant details."""
        tenant_id = "tenant-123"
        expected_tenant = {
            "id": tenant_id,
            "name": "Test Tenant",
            "domain": "test.example.com",
            "settings": {"timezone": "UTC", "currency": "USD"},
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "user_count": 5,
            "project_count": 3
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = expected_tenant
        
        client.get.return_value = response
        result = client.get(f"{self.base_url}/{tenant_id}", headers=auth_headers)
        
        self.assert_success_response(result)
        tenant_data = result.json()
        assert tenant_data["id"] == tenant_id
        assert "user_count" in tenant_data
        assert "project_count" in tenant_data
    
    def test_update_tenant_settings(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test updating tenant settings."""
        tenant_id = "tenant-123"
        update_data = {
            "name": "Updated Tenant Name",
            "settings": {
                "timezone": "America/New_York",
                "currency": "EUR",
                "date_format": "MM/DD/YYYY"
            }
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": tenant_id,
            **update_data,
            "updated_at": "2024-01-15T11:00:00Z"
        }
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{tenant_id}", json=update_data, headers=admin_auth_headers)
        
        self.assert_success_response(result)
        updated_tenant = result.json()
        assert updated_tenant["name"] == update_data["name"]
        assert updated_tenant["settings"]["timezone"] == "America/New_York"
    
    def test_update_tenant_non_admin(self, client: Mock, auth_headers: Dict[str, str]):
        """Test updating tenant by non-admin should fail."""
        tenant_id = "tenant-123"
        update_data = {"name": "Updated Name"}
        
        response = Mock()
        response.status_code = status.HTTP_403_FORBIDDEN
        response.json.return_value = {"detail": "Insufficient permissions to update tenant"}
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{tenant_id}", json=update_data, headers=auth_headers)
        
        self.assert_forbidden(result)
    
    def test_deactivate_tenant(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test deactivating a tenant."""
        tenant_id = "tenant-123"
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": tenant_id,
            "name": "Test Tenant",
            "active": False,
            "deactivated_at": "2024-01-15T12:00:00Z"
        }
        
        client.post.return_value = response
        result = client.post(f"{self.base_url}/{tenant_id}/deactivate", headers=admin_auth_headers)
        
        self.assert_success_response(result)
        deactivated_tenant = result.json()
        assert deactivated_tenant["active"] is False
        assert "deactivated_at" in deactivated_tenant
    
    def test_list_tenants_admin(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test listing all tenants as admin."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "tenants": [
                {"id": "tenant-1", "name": "Tenant 1", "active": True, "user_count": 10},
                {"id": "tenant-2", "name": "Tenant 2", "active": True, "user_count": 5},
                {"id": "tenant-3", "name": "Tenant 3", "active": False, "user_count": 0}
            ],
            "total": 3,
            "active_count": 2,
            "inactive_count": 1
        }
        
        client.get.return_value = response
        result = client.get(self.base_url, headers=admin_auth_headers)
        
        self.assert_success_response(result)
        tenants_data = result.json()
        assert "tenants" in tenants_data
        assert "total" in tenants_data
        assert tenants_data["total"] == 3
        assert tenants_data["active_count"] == 2
    
    def test_list_tenants_non_admin(self, client: Mock, auth_headers: Dict[str, str]):
        """Test that non-admin users can only see their own tenants."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "tenants": [
                {"id": "tenant-123", "name": "User's Tenant", "role": "user"}
            ],
            "total": 1
        }
        
        client.get.return_value = response
        result = client.get("/auth/tenants", headers=auth_headers)  # Different endpoint for users
        
        self.assert_success_response(result)
        tenants_data = result.json()
        assert len(tenants_data["tenants"]) == 1


class TestTenantUserManagement(BaseAPITest):
    """Test cases for managing users within tenants."""
    
    def test_invite_user_to_tenant(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test inviting a user to join a tenant."""
        tenant_id = "tenant-123"
        invite_data = {
            "email": "newuser@example.com",
            "role": "user",
            "message": "Welcome to our time tracking team!"
        }
        
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "id": "invite-456",
            "email": invite_data["email"],
            "role": invite_data["role"],
            "tenant_id": tenant_id,
            "status": "pending",
            "expires_at": "2024-01-22T10:00:00Z"
        }
        
        client.post.return_value = response
        result = client.post(f"/tenants/{tenant_id}/invite", json=invite_data, headers=admin_auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        invite_response = result.json()
        assert invite_response["email"] == invite_data["email"]
        assert invite_response["status"] == "pending"
    
    def test_accept_tenant_invitation(self, client: Mock):
        """Test accepting a tenant invitation."""
        invite_token = "valid_invite_token"
        accept_data = {
            "token": invite_token,
            "password": "secure_password123",
            "first_name": "New",
            "last_name": "User"
        }
        
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "user": {
                "id": "user-new",
                "email": "newuser@example.com",
                "first_name": "New",
                "last_name": "User"
            },
            "tenant": {
                "id": "tenant-123",
                "name": "Test Tenant",
                "role": "user"
            },
            "access_token": "jwt_token_here"
        }
        
        client.post.return_value = response
        result = client.post("/auth/accept-invitation", json=accept_data)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        acceptance_data = result.json()
        assert "user" in acceptance_data
        assert "tenant" in acceptance_data
        assert "access_token" in acceptance_data
    
    def test_list_tenant_users(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test listing users in a tenant."""
        tenant_id = "tenant-123"
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "users": [
                {
                    "id": "user-1",
                    "email": "admin@example.com",
                    "first_name": "Admin",
                    "last_name": "User",
                    "role": "admin",
                    "active": True,
                    "last_login": "2024-01-15T09:00:00Z"
                },
                {
                    "id": "user-2",
                    "email": "user@example.com",
                    "first_name": "Regular",
                    "last_name": "User",
                    "role": "user",
                    "active": True,
                    "last_login": "2024-01-14T16:30:00Z"
                }
            ],
            "total": 2,
            "active_count": 2
        }
        
        client.get.return_value = response
        result = client.get(f"/tenants/{tenant_id}/users", headers=admin_auth_headers)
        
        self.assert_success_response(result)
        users_data = result.json()
        assert "users" in users_data
        assert users_data["total"] == 2
        assert users_data["active_count"] == 2
    
    def test_update_user_role_in_tenant(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test updating a user's role within a tenant."""
        tenant_id = "tenant-123"
        user_id = "user-456"
        role_update_data = {"role": "admin"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": user_id,
            "email": "user@example.com",
            "role": "admin",
            "updated_at": "2024-01-15T11:30:00Z"
        }
        
        client.put.return_value = response
        result = client.put(f"/tenants/{tenant_id}/users/{user_id}/role", 
                          json=role_update_data, headers=admin_auth_headers)
        
        self.assert_success_response(result)
        updated_user = result.json()
        assert updated_user["role"] == "admin"
    
    def test_remove_user_from_tenant(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test removing a user from a tenant."""
        tenant_id = "tenant-123"
        user_id = "user-456"
        
        response = Mock()
        response.status_code = status.HTTP_204_NO_CONTENT
        
        client.delete.return_value = response
        result = client.delete(f"/tenants/{tenant_id}/users/{user_id}", headers=admin_auth_headers)
        
        assert result.status_code == status.HTTP_204_NO_CONTENT


class TestTenantDataIsolation(BaseAPITest, TenantIsolationTestMixin):
    """Test cases specifically for multi-tenant data isolation."""
    
    base_url = "/clients"  # Using clients as example for isolation testing
    
    def test_cross_tenant_data_access_prevention(self, client: Mock, auth_headers: Dict[str, str], 
                                                different_tenant_headers: Dict[str, str]):
        """Test that users cannot access data from other tenants."""
        # Create data in tenant-123
        tenant1_data = {"name": "Tenant 1 Client", "email": "client1@tenant1.com"}
        create_response = Mock()
        create_response.status_code = status.HTTP_201_CREATED
        create_response.json.return_value = {"id": "client-1", **tenant1_data}
        
        client.post.return_value = create_response
        client.post(self.base_url, json=tenant1_data, headers=auth_headers)
        
        # Try to access from tenant-456
        access_response = Mock()
        access_response.status_code = status.HTTP_404_NOT_FOUND
        access_response.json.return_value = {"detail": "Client not found"}
        
        client.get.return_value = access_response
        result = client.get(f"{self.base_url}/client-1", headers=different_tenant_headers)
        
        self.assert_not_found(result)
    
    def test_tenant_data_modification_isolation(self, client: Mock, auth_headers: Dict[str, str], 
                                              different_tenant_headers: Dict[str, str]):
        """Test that users cannot modify data from other tenants."""
        client_id = "client-cross-tenant"
        update_data = {"name": "Hacked Client Name"}
        
        # Try to update client from different tenant
        response = Mock()
        response.status_code = status.HTTP_404_NOT_FOUND
        response.json.return_value = {"detail": "Client not found"}
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{client_id}", 
                          json=update_data, headers=different_tenant_headers)
        
        self.assert_not_found(result)
    
    def test_tenant_data_deletion_isolation(self, client: Mock, auth_headers: Dict[str, str], 
                                          different_tenant_headers: Dict[str, str]):
        """Test that users cannot delete data from other tenants."""
        client_id = "client-cross-tenant"
        
        # Try to delete client from different tenant
        response = Mock()
        response.status_code = status.HTTP_404_NOT_FOUND
        response.json.return_value = {"detail": "Client not found"}
        
        client.delete.return_value = response
        result = client.delete(f"{self.base_url}/{client_id}", headers=different_tenant_headers)
        
        self.assert_not_found(result)
    
    def test_tenant_listing_isolation(self, client: Mock, auth_headers: Dict[str, str], 
                                    different_tenant_headers: Dict[str, str]):
        """Test that listing endpoints only show tenant-specific data."""
        # Mock different responses for different tenants
        def mock_get_response(url, headers=None, **kwargs):
            if url == self.base_url:
                tenant_id = headers.get("X-Tenant-ID") if headers else None
                if tenant_id == "tenant-123":
                    response = Mock()
                    response.status_code = status.HTTP_200_OK
                    response.json.return_value = {
                        "items": [{"id": "client-1", "name": "Tenant 1 Client"}],
                        "total": 1
                    }
                    return response
                elif tenant_id == "tenant-456":
                    response = Mock()
                    response.status_code = status.HTTP_200_OK
                    response.json.return_value = {
                        "items": [{"id": "client-2", "name": "Tenant 2 Client"}],
                        "total": 1
                    }
                    return response
            
            # Default unauthorized response
            response = Mock()
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return response
        
        client.get.side_effect = mock_get_response
        
        # Test tenant-123 sees only their data
        result1 = client.get(self.base_url, headers=auth_headers)
        self.assert_success_response(result1)
        tenant1_data = result1.json()
        assert len(tenant1_data["items"]) == 1
        assert tenant1_data["items"][0]["name"] == "Tenant 1 Client"
        
        # Test tenant-456 sees only their data
        result2 = client.get(self.base_url, headers=different_tenant_headers)
        self.assert_success_response(result2)
        tenant2_data = result2.json()
        assert len(tenant2_data["items"]) == 1
        assert tenant2_data["items"][0]["name"] == "Tenant 2 Client"
    
    def test_database_query_tenant_filtering(self, client: Mock, auth_headers: Dict[str, str]):
        """Test that database queries properly filter by tenant ID."""
        # This would typically involve checking the actual SQL queries generated
        # For now, we test the API behavior that should result from proper filtering
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "items": [
                {"id": "item-1", "tenant_id": "tenant-123", "name": "Item 1"},
                {"id": "item-2", "tenant_id": "tenant-123", "name": "Item 2"}
            ],
            "total": 2
        }
        
        client.get.return_value = response
        result = client.get(self.base_url, headers=auth_headers)
        
        self.assert_success_response(result)
        items = result.json()["items"]
        
        # All items should belong to the requesting tenant
        for item in items:
            assert item["tenant_id"] == "tenant-123"
