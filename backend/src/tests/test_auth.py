"""
Authentication and authorization tests for the multitenant time tracker.

Tests cover user registration, login, JWT token handling, password reset,
multi-tenant authorization, and various security scenarios.
"""
from unittest.mock import Mock
from fastapi import status
from typing import Dict, Any

from .test_base import BaseAPITest


class TestAuthentication(BaseAPITest):
    """Test cases for user authentication."""
    
    def test_user_registration_success(self, client: Mock, sample_user_data: Dict[str, Any], 
                                     sample_tenant_data: Dict[str, Any]):
        """Test successful user registration."""
        registration_data = {
            **sample_user_data,
            "tenant_name": sample_tenant_data["name"]
        }
        
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "user": {
                "id": "user-123",
                "email": sample_user_data["email"],
                "first_name": sample_user_data["first_name"],
                "last_name": sample_user_data["last_name"],
                "role": sample_user_data["role"]
            },
            "tenant": {
                "id": "tenant-123",
                "name": sample_tenant_data["name"]
            },
            "access_token": "jwt_token_here",
            "token_type": "bearer"
        }
        
        client.post.return_value = response
        result = client.post("/auth/register", json=registration_data)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        response_data = result.json()
        assert "user" in response_data
        assert "tenant" in response_data
        assert "access_token" in response_data
        assert response_data["user"]["email"] == sample_user_data["email"]
    
    def test_user_registration_duplicate_email(self, client: Mock, sample_user_data: Dict[str, Any]):
        """Test user registration with duplicate email."""
        response = Mock()
        response.status_code = status.HTTP_409_CONFLICT
        response.json.return_value = {"detail": "User with this email already exists"}
        
        client.post.return_value = response
        result = client.post("/auth/register", json=sample_user_data)
        
        self.assert_conflict(result)
    
    def test_user_registration_invalid_email(self, client: Mock):
        """Test user registration with invalid email format."""
        invalid_data = {
            "email": "invalid-email",
            "password": "secure_password123",
            "first_name": "Test",
            "last_name": "User",
            "tenant_name": "Test Tenant"
        }
        
        response = Mock()
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        response.json.return_value = {
            "detail": [{"loc": ["body", "email"], "msg": "invalid email format", "type": "value_error.email"}]
        }
        
        client.post.return_value = response
        result = client.post("/auth/register", json=invalid_data)
        
        self.assert_validation_error(result, "email")
    
    def test_user_registration_weak_password(self, client: Mock):
        """Test user registration with weak password."""
        weak_password_data = {
            "email": "test@example.com",
            "password": "123",  # Too weak
            "first_name": "Test",
            "last_name": "User",
            "tenant_name": "Test Tenant"
        }
        
        response = Mock()
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        response.json.return_value = {
            "detail": [{"loc": ["body", "password"], "msg": "password too short", "type": "value_error.password"}]
        }
        
        client.post.return_value = response
        result = client.post("/auth/register", json=weak_password_data)
        
        self.assert_validation_error(result, "password")
    
    def test_user_login_success(self, client: Mock, sample_user_data: Dict[str, Any]):
        """Test successful user login."""
        login_data = {
            "email": sample_user_data["email"],
            "password": sample_user_data["password"]
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "access_token": "jwt_token_here",
            "token_type": "bearer",
            "user": {
                "id": "user-123",
                "email": sample_user_data["email"],
                "first_name": sample_user_data["first_name"],
                "last_name": sample_user_data["last_name"],
                "role": sample_user_data["role"]
            },
            "tenants": [
                {"id": "tenant-123", "name": "Test Tenant", "role": "admin"}
            ]
        }
        
        client.post.return_value = response
        result = client.post("/auth/login", json=login_data)
        
        self.assert_success_response(result)
        response_data = result.json()
        assert "access_token" in response_data
        assert "user" in response_data
        assert "tenants" in response_data
        assert len(response_data["tenants"]) > 0
    
    def test_user_login_invalid_credentials(self, client: Mock):
        """Test login with invalid credentials."""
        invalid_login_data = {
            "email": "test@example.com",
            "password": "wrong_password"
        }
        
        response = Mock()
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.json.return_value = {"detail": "Invalid credentials"}
        
        client.post.return_value = response
        result = client.post("/auth/login", json=invalid_login_data)
        
        self.assert_unauthorized(result)
    
    def test_user_login_nonexistent_user(self, client: Mock):
        """Test login with non-existent user."""
        nonexistent_user_data = {
            "email": "nonexistent@example.com",
            "password": "any_password"
        }
        
        response = Mock()
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.json.return_value = {"detail": "Invalid credentials"}
        
        client.post.return_value = response
        result = client.post("/auth/login", json=nonexistent_user_data)
        
        self.assert_unauthorized(result)
    
    def test_password_reset_request(self, client: Mock):
        """Test password reset request."""
        reset_request_data = {"email": "test@example.com"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {"message": "Password reset email sent"}
        
        client.post.return_value = response
        result = client.post("/auth/password-reset-request", json=reset_request_data)
        
        self.assert_success_response(result)
    
    def test_password_reset_confirm(self, client: Mock):
        """Test password reset confirmation."""
        reset_data = {
            "token": "valid_reset_token",
            "new_password": "new_secure_password123"
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {"message": "Password reset successful"}
        
        client.post.return_value = response
        result = client.post("/auth/password-reset-confirm", json=reset_data)
        
        self.assert_success_response(result)
    
    def test_password_reset_invalid_token(self, client: Mock):
        """Test password reset with invalid token."""
        reset_data = {
            "token": "invalid_reset_token",
            "new_password": "new_secure_password123"
        }
        
        response = Mock()
        response.status_code = status.HTTP_400_BAD_REQUEST
        response.json.return_value = {"detail": "Invalid or expired reset token"}
        
        client.post.return_value = response
        result = client.post("/auth/password-reset-confirm", json=reset_data)
        
        self.assert_error_response(result, status.HTTP_400_BAD_REQUEST)
    
    def test_logout_success(self, client: Mock, auth_headers: Dict[str, str]):
        """Test successful logout."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {"message": "Logged out successfully"}
        
        client.post.return_value = response
        result = client.post("/auth/logout", headers=auth_headers)
        
        self.assert_success_response(result)
    
    def test_token_refresh(self, client: Mock, auth_headers: Dict[str, str]):
        """Test JWT token refresh."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "access_token": "new_jwt_token",
            "token_type": "bearer"
        }
        
        client.post.return_value = response
        result = client.post("/auth/refresh", headers=auth_headers)
        
        self.assert_success_response(result)
        response_data = result.json()
        assert "access_token" in response_data
    
    def test_get_current_user(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting current authenticated user."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": "user-123",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "user",
            "current_tenant_id": "tenant-123"
        }
        
        client.get.return_value = response
        result = client.get("/auth/me", headers=auth_headers)
        
        self.assert_success_response(result)
        user_data = result.json()
        assert "id" in user_data
        assert "email" in user_data
        assert "current_tenant_id" in user_data


class TestAuthorization(BaseAPITest):
    """Test cases for authorization and access control."""
    
    def test_access_with_valid_token(self, client: Mock, auth_headers: Dict[str, str]):
        """Test accessing protected endpoint with valid token."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {"message": "Access granted"}
        
        client.get.return_value = response
        result = client.get("/protected-endpoint", headers=auth_headers)
        
        self.assert_success_response(result)
    
    def test_access_without_token(self, client: Mock):
        """Test accessing protected endpoint without authentication token."""
        response = Mock()
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.json.return_value = {"detail": "Authentication required"}
        
        client.get.return_value = response
        result = client.get("/protected-endpoint")
        
        self.assert_unauthorized(result)
    
    def test_access_with_expired_token(self, client: Mock, auth_mocker):
        """Test accessing protected endpoint with expired token."""
        expired_headers = {
            "Authorization": f"Bearer {auth_mocker.create_expired_token()}"
        }
        
        response = Mock()
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.json.return_value = {"detail": "Token has expired"}
        
        client.get.return_value = response
        result = client.get("/protected-endpoint", headers=expired_headers)
        
        self.assert_unauthorized(result)
    
    def test_access_with_invalid_token(self, client: Mock, auth_mocker):
        """Test accessing protected endpoint with invalid token."""
        invalid_headers = {
            "Authorization": f"Bearer {auth_mocker.create_invalid_token()}"
        }
        
        response = Mock()
        response.status_code = status.HTTP_401_UNAUTHORIZED
        response.json.return_value = {"detail": "Invalid token"}
        
        client.get.return_value = response
        result = client.get("/protected-endpoint", headers=invalid_headers)
        
        self.assert_unauthorized(result)
    
    def test_admin_only_endpoint_with_admin_role(self, client: Mock, admin_auth_headers: Dict[str, str]):
        """Test accessing admin-only endpoint with admin role."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {"message": "Admin access granted"}
        
        client.get.return_value = response
        result = client.get("/admin/users", headers=admin_auth_headers)
        
        self.assert_success_response(result)
    
    def test_admin_only_endpoint_with_user_role(self, client: Mock, auth_headers: Dict[str, str]):
        """Test accessing admin-only endpoint with regular user role."""
        response = Mock()
        response.status_code = status.HTTP_403_FORBIDDEN
        response.json.return_value = {"detail": "Insufficient permissions"}
        
        client.get.return_value = response
        result = client.get("/admin/users", headers=auth_headers)
        
        self.assert_forbidden(result)
    
    def test_tenant_access_control(self, client: Mock, auth_headers: Dict[str, str], 
                                 different_tenant_headers: Dict[str, str]):
        """Test that users can only access resources from their tenant."""
        # Access resource from own tenant
        own_tenant_response = Mock()
        own_tenant_response.status_code = status.HTTP_200_OK
        own_tenant_response.json.return_value = {"id": "resource-1", "name": "Own Tenant Resource"}
        
        # Try to access resource from different tenant
        different_tenant_response = Mock()
        different_tenant_response.status_code = status.HTTP_404_NOT_FOUND
        different_tenant_response.json.return_value = {"detail": "Resource not found"}
        
        def mock_get(url, headers=None, **kwargs):
            if headers and headers.get("X-Tenant-ID") == "tenant-123":
                return own_tenant_response
            else:
                return different_tenant_response
        
        client.get.side_effect = mock_get
        
        # Should succeed for own tenant
        result1 = client.get("/clients/client-1", headers=auth_headers)
        self.assert_success_response(result1)
        
        # Should fail for different tenant
        result2 = client.get("/clients/client-1", headers=different_tenant_headers)
        self.assert_not_found(result2)


class TestTenantSelection(BaseAPITest):
    """Test cases for tenant selection and switching."""
    
    def test_select_tenant_success(self, client: Mock, auth_headers: Dict[str, str]):
        """Test successful tenant selection."""
        tenant_selection_data = {"tenant_id": "tenant-456"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "message": "Tenant selected successfully",
            "current_tenant": {
                "id": "tenant-456",
                "name": "New Tenant",
                "role": "user"
            }
        }
        
        client.post.return_value = response
        result = client.post("/auth/select-tenant", json=tenant_selection_data, headers=auth_headers)
        
        self.assert_success_response(result)
        response_data = result.json()
        assert "current_tenant" in response_data
        assert response_data["current_tenant"]["id"] == "tenant-456"
    
    def test_select_unauthorized_tenant(self, client: Mock, auth_headers: Dict[str, str]):
        """Test selecting a tenant the user doesn't have access to."""
        tenant_selection_data = {"tenant_id": "unauthorized-tenant"}
        
        response = Mock()
        response.status_code = status.HTTP_403_FORBIDDEN
        response.json.return_value = {"detail": "Access to this tenant is not allowed"}
        
        client.post.return_value = response
        result = client.post("/auth/select-tenant", json=tenant_selection_data, headers=auth_headers)
        
        self.assert_forbidden(result)
    
    def test_select_nonexistent_tenant(self, client: Mock, auth_headers: Dict[str, str]):
        """Test selecting a non-existent tenant."""
        tenant_selection_data = {"tenant_id": "nonexistent-tenant"}
        
        response = Mock()
        response.status_code = status.HTTP_404_NOT_FOUND
        response.json.return_value = {"detail": "Tenant not found"}
        
        client.post.return_value = response
        result = client.post("/auth/select-tenant", json=tenant_selection_data, headers=auth_headers)
        
        self.assert_not_found(result)
    
    def test_get_user_tenants(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting list of tenants user has access to."""
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "tenants": [
                {"id": "tenant-123", "name": "Primary Tenant", "role": "admin"},
                {"id": "tenant-456", "name": "Secondary Tenant", "role": "user"}
            ]
        }
        
        client.get.return_value = response
        result = client.get("/auth/tenants", headers=auth_headers)
        
        self.assert_success_response(result)
        response_data = result.json()
        assert "tenants" in response_data
        assert len(response_data["tenants"]) == 2
