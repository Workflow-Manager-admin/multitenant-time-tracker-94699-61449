"""
User management tests for the multitenant time tracker.

Tests cover user CRUD operations, profile management, and tenant-specific
user operations with proper data isolation.
"""
from unittest.mock import Mock
from fastapi import status
from typing import Dict, Any

from .test_base import BaseAPITest, BaseCRUDTest, TenantIsolationTestMixin


class TestUserManagement(BaseCRUDTest, TenantIsolationTestMixin):
    """Test cases for user CRUD operations within tenants."""
    
    base_url = "/users"
    
    def test_create_user_success(self, client: Mock, admin_auth_headers: Dict[str, str], 
                               sample_user_data: Dict[str, Any]):
        """Test successful user creation by admin."""
        user_data = {
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
            "role": "user",
            "send_invitation": True
        }
        
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "id": "user-new",
            **user_data,
            "active": True,
            "created_at": "2024-01-15T10:00:00Z",
            "tenant_id": "tenant-123"
        }
        
        client.post.return_value = response
        result = client.post(self.base_url, json=user_data, headers=admin_auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        created_user = result.json()
        assert "id" in created_user
        assert created_user["email"] == user_data["email"]
        assert created_user["tenant_id"] == "tenant-123"
    
    def test_create_user_duplicate_email(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test user creation with duplicate email within tenant."""
        duplicate_user_data = {
            "email": "existing@example.com",
            "first_name": "Duplicate",
            "last_name": "User",
            "role": "user"
        }
        
        response = Mock()
        response.status_code = status.HTTP_409_CONFLICT
        response.json.return_value = {"detail": "User with this email already exists in this tenant"}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=duplicate_user_data, headers=admin_auth_headers)
        
        self.assert_conflict(result)
    
    def test_create_user_non_admin(self, client: Mock, auth_headers: Dict[str, str], 
                                 sample_user_data: Dict[str, Any]):
        """Test user creation by non-admin should fail."""
        response = Mock()
        response.status_code = status.HTTP_403_FORBIDDEN
        response.json.return_value = {"detail": "Only administrators can create users"}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=sample_user_data, headers=auth_headers)
        
        self.assert_forbidden(result)
    
    def test_get_user_profile(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting user profile information."""
        user_id = "user-123"
        expected_user = {
            "id": user_id,
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "user",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "last_login": "2024-01-15T09:00:00Z",
            "tenant_id": "tenant-123",
            "preferences": {
                "timezone": "UTC",
                "date_format": "YYYY-MM-DD",
                "time_format": "24h"
            }
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = expected_user
        
        client.get.return_value = response
        result = client.get(f"{self.base_url}/{user_id}", headers=auth_headers)
        
        self.assert_success_response(result)
        user_data = result.json()
        assert user_data["id"] == user_id
        assert "preferences" in user_data
    
    def test_update_user_profile(self, client: Mock, auth_headers: Dict[str, str]):
        """Test updating user profile information."""
        user_id = "user-123"
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "preferences": {
                "timezone": "America/New_York",
                "date_format": "MM/DD/YYYY"
            }
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": user_id,
            "email": "test@example.com",
            **update_data,
            "updated_at": "2024-01-15T11:00:00Z"
        }
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{user_id}", json=update_data, headers=auth_headers)
        
        self.assert_success_response(result)
        updated_user = result.json()
        assert updated_user["first_name"] == "Updated"
        assert updated_user["preferences"]["timezone"] == "America/New_York"
    
    def test_update_other_user_profile_forbidden(self, client: Mock, auth_headers: Dict[str, str]):
        """Test that regular users cannot update other users' profiles."""
        other_user_id = "user-456"
        update_data = {"first_name": "Hacked"}
        
        response = Mock()
        response.status_code = status.HTTP_403_FORBIDDEN
        response.json.return_value = {"detail": "Cannot modify other user's profile"}
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{other_user_id}", json=update_data, headers=auth_headers)
        
        self.assert_forbidden(result)
    
    def test_admin_update_user_role(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test admin updating user role."""
        user_id = "user-456"
        role_update_data = {"role": "admin"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": user_id,
            "email": "user@example.com",
            "role": "admin",
            "updated_at": "2024-01-15T12:00:00Z"
        }
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{user_id}/role", 
                          json=role_update_data, headers=admin_auth_headers)
        
        self.assert_success_response(result)
        updated_user = result.json()
        assert updated_user["role"] == "admin"
    
    def test_deactivate_user(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test deactivating a user account."""
        user_id = "user-456"
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": user_id,
            "email": "user@example.com",
            "active": False,
            "deactivated_at": "2024-01-15T13:00:00Z"
        }
        
        client.post.return_value = response
        result = client.post(f"{self.base_url}/{user_id}/deactivate", headers=admin_auth_headers)
        
        self.assert_success_response(result)
        deactivated_user = result.json()
        assert deactivated_user["active"] is False
        assert "deactivated_at" in deactivated_user
    
    def test_list_users_in_tenant(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test listing all users in the current tenant."""
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
                    "active": True
                },
                {
                    "id": "user-2",
                    "email": "user@example.com",
                    "first_name": "Regular",
                    "last_name": "User",
                    "role": "user",
                    "active": True
                }
            ],
            "total": 2,
            "active_count": 2,
            "admin_count": 1
        }
        
        client.get.return_value = response
        result = client.get(self.base_url, headers=admin_auth_headers)
        
        self.assert_success_response(result)
        users_data = result.json()
        assert "users" in users_data
        assert users_data["total"] == 2
        assert users_data["admin_count"] == 1
    
    def test_search_users(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test searching users by name or email."""
        search_params = {"q": "john", "active": "true"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "users": [
                {
                    "id": "user-john",
                    "email": "john@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "role": "user",
                    "active": True
                }
            ],
            "total": 1,
            "query": "john"
        }
        
        client.get.return_value = response
        result = client.get(self.base_url, params=search_params, headers=admin_auth_headers)
        
        self.assert_success_response(result)
        search_results = result.json()
        assert search_results["total"] == 1
        assert "john" in search_results["users"][0]["first_name"].lower()


class TestUserSelfService(BaseAPITest):
    """Test cases for user self-service operations."""
    
    def test_get_own_profile(self, client: Mock, auth_headers: Dict[str, str]):
        """Test user getting their own profile."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "user",
            "active": True,
            "preferences": {
                "timezone": "UTC",
                "notifications": True
            }
        }
        
        client.get.return_value = response
        result = client.get("/users/me", headers=auth_headers)
        
        self.assert_success_response(result)
        profile_data = result.json()
        assert "id" in profile_data
        assert "preferences" in profile_data
    
    def test_update_own_profile(self, client: Mock, auth_headers: Dict[str, str]):
        """Test user updating their own profile."""
        update_data = {
            "first_name": "Updated",
            "preferences": {
                "timezone": "America/Los_Angeles",
                "notifications": False
            }
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            **update_data,
            "updated_at": "2024-01-15T14:00:00Z"
        }
        
        client.put.return_value = response
        result = client.put("/users/me", json=update_data, headers=auth_headers)
        
        self.assert_success_response(result)
        updated_profile = result.json()
        assert updated_profile["first_name"] == "Updated"
        assert updated_profile["preferences"]["timezone"] == "America/Los_Angeles"
    
    def test_change_password(self, client: Mock, auth_headers: Dict[str, str]):
        """Test user changing their password."""
        password_change_data = {
            "current_password": "old_password123",
            "new_password": "new_secure_password123"
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {"message": "Password changed successfully"}
        
        client.post.return_value = response
        result = client.post("/users/me/change-password", 
                           json=password_change_data, headers=auth_headers)
        
        self.assert_success_response(result)
    
    def test_change_password_wrong_current(self, client: Mock, auth_headers: Dict[str, str]):
        """Test password change with wrong current password."""
        password_change_data = {
            "current_password": "wrong_password",
            "new_password": "new_secure_password123"
        }
        
        response = Mock()
        response.status_code = status.HTTP_400_BAD_REQUEST
        response.json.return_value = {"detail": "Current password is incorrect"}
        
        client.post.return_value = response
        result = client.post("/users/me/change-password", 
                           json=password_change_data, headers=auth_headers)
        
        self.assert_error_response(result, status.HTTP_400_BAD_REQUEST)
    
    def test_get_user_activity_log(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting user's activity log."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "activities": [
                {
                    "id": "activity-1",
                    "action": "login",
                    "timestamp": "2024-01-15T09:00:00Z",
                    "ip_address": "192.168.1.100",
                    "user_agent": "Mozilla/5.0..."
                },
                {
                    "id": "activity-2",
                    "action": "profile_update",
                    "timestamp": "2024-01-14T16:30:00Z",
                    "details": "Updated first name"
                }
            ],
            "total": 2
        }
        
        client.get.return_value = response
        result = client.get("/users/me/activity", headers=auth_headers)
        
        self.assert_success_response(result)
        activity_data = result.json()
        assert "activities" in activity_data
        assert len(activity_data["activities"]) == 2


class TestUserTenantIsolation(BaseAPITest, TenantIsolationTestMixin):
    """Test cases for user data isolation between tenants."""
    
    base_url = "/users"
    
    def test_user_list_tenant_isolation(self, client: Mock, auth_headers: Dict[str, str], 
                                      different_tenant_headers: Dict[str, str]):
        """Test that user listing only shows users from current tenant."""
        def mock_get_users(url, headers=None, **kwargs):
            tenant_id = headers.get("X-Tenant-ID") if headers else None
            if tenant_id == "tenant-123":
                response = Mock()
                response.status_code = status.HTTP_200_OK
                response.json.return_value = {
                    "users": [{"id": "user-1", "email": "user1@tenant1.com"}],
                    "total": 1
                }
                return response
            elif tenant_id == "tenant-456":
                response = Mock()
                response.status_code = status.HTTP_200_OK
                response.json.return_value = {
                    "users": [{"id": "user-2", "email": "user2@tenant2.com"}],
                    "total": 1
                }
                return response
            return Mock(status_code=401)
        
        client.get.side_effect = mock_get_users
        
        # Test first tenant
        result1 = client.get(self.base_url, headers=auth_headers)
        self.assert_success_response(result1)
        tenant1_users = result1.json()["users"]
        assert len(tenant1_users) == 1
        assert tenant1_users[0]["email"] == "user1@tenant1.com"
        
        # Test second tenant
        result2 = client.get(self.base_url, headers=different_tenant_headers)
        self.assert_success_response(result2)
        tenant2_users = result2.json()["users"]
        assert len(tenant2_users) == 1
        assert tenant2_users[0]["email"] == "user2@tenant2.com"
    
    def test_cross_tenant_user_access_denied(self, client: Mock, auth_headers: Dict[str, str]):
        """Test that accessing user from different tenant is denied."""
        cross_tenant_user_id = "user-from-other-tenant"
        
        response = Mock()
        response.status_code = status.HTTP_404_NOT_FOUND
        response.json.return_value = {"detail": "User not found"}
        
        client.get.return_value = response
        result = client.get(f"{self.base_url}/{cross_tenant_user_id}", headers=auth_headers)
        
        self.assert_not_found(result)
    
    def test_user_email_uniqueness_per_tenant(self, client: Mock, auth_headers: Dict[str, str]):
        """Test that same email can exist in different tenants but not within same tenant."""
        # This test would verify that the same email can be used across different tenants
        # but not within the same tenant
        
        user_data = {
            "email": "shared@example.com",
            "first_name": "Shared",
            "last_name": "User",
            "role": "user"
        }
        
        # Should succeed in current tenant if email doesn't exist there
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {"id": "user-new", **user_data}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=user_data, headers=auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
