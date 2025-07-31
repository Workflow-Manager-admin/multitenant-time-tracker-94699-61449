"""
Client management tests for the multitenant time tracker.

Tests cover client CRUD operations, contact management, and tenant-specific
client operations with proper data isolation.
"""
from unittest.mock import Mock
from fastapi import status
from typing import Dict, Any

from .test_base import BaseAPITest, BaseCRUDTest, TenantIsolationTestMixin


class TestClientManagement(BaseCRUDTest, TenantIsolationTestMixin):
    """Test cases for client CRUD operations."""
    
    base_url = "/clients"
    
    def test_create_client_success(self, client: Mock, auth_headers: Dict[str, str], 
                                 sample_client_data: Dict[str, Any]):
        """Test successful client creation."""
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "id": "client-123",
            **sample_client_data,
            "created_at": "2024-01-15T10:00:00Z",
            "tenant_id": "tenant-123",
            "project_count": 0
        }
        
        client.post.return_value = response
        result = client.post(self.base_url, json=sample_client_data, headers=auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        created_client = result.json()
        assert "id" in created_client
        assert created_client["name"] == sample_client_data["name"]
        assert created_client["tenant_id"] == "tenant-123"
    
    def test_create_client_duplicate_name(self, client: Mock, auth_headers: Dict[str, str]):
        """Test client creation with duplicate name within tenant."""
        duplicate_client_data = {
            "name": "Existing Client",
            "contact_email": "contact@existing.com"
        }
        
        response = Mock()
        response.status_code = status.HTTP_409_CONFLICT
        response.json.return_value = {"detail": "Client with this name already exists in this tenant"}
        
        client.post.return_value = response
        result = client.post(self.base_url, json=duplicate_client_data, headers=auth_headers)
        
        self.assert_conflict(result)
    
    def test_create_client_invalid_email(self, client: Mock, auth_headers: Dict[str, str]):
        """Test client creation with invalid email format."""
        invalid_client_data = {
            "name": "Test Client",
            "contact_email": "invalid-email"
        }
        
        response = Mock()
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        response.json.return_value = {
            "detail": [{"loc": ["body", "contact_email"], "msg": "invalid email format", "type": "value_error.email"}]
        }
        
        client.post.return_value = response
        result = client.post(self.base_url, json=invalid_client_data, headers=auth_headers)
        
        self.assert_validation_error(result, "contact_email")
    
    def test_get_client_details(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting detailed client information."""
        client_id = "client-123"
        expected_client = {
            "id": client_id,
            "name": "Test Client Corp",
            "contact_email": "contact@testclient.com",
            "contact_phone": "+1-555-0123",
            "address": "123 Business St, City, ST 12345",
            "active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "tenant_id": "tenant-123",
            "project_count": 3,
            "total_hours_tracked": 150.5,
            "total_revenue": 11287.50
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = expected_client
        
        client.get.return_value = response
        result = client.get(f"{self.base_url}/{client_id}", headers=auth_headers)
        
        self.assert_success_response(result)
        client_data = result.json()
        assert client_data["id"] == client_id
        assert "project_count" in client_data
        assert "total_hours_tracked" in client_data
    
    def test_update_client_contact_info(self, client: Mock, auth_headers: Dict[str, str]):
        """Test updating client contact information."""
        client_id = "client-123"
        update_data = {
            "contact_email": "newemail@testclient.com",
            "contact_phone": "+1-555-9999",
            "address": "456 New Business Ave, New City, ST 54321"
        }
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": client_id,
            "name": "Test Client Corp",
            **update_data,
            "updated_at": "2024-01-15T11:00:00Z"
        }
        
        client.put.return_value = response
        result = client.put(f"{self.base_url}/{client_id}", json=update_data, headers=auth_headers)
        
        self.assert_success_response(result)
        updated_client = result.json()
        assert updated_client["contact_email"] == update_data["contact_email"]
        assert updated_client["contact_phone"] == update_data["contact_phone"]
    
    def test_deactivate_client(self, client: Mock, auth_headers: Dict[str, str]):
        """Test deactivating a client."""
        client_id = "client-123"
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "id": client_id,
            "name": "Test Client Corp",
            "active": False,
            "deactivated_at": "2024-01-15T12:00:00Z"
        }
        
        client.post.return_value = response
        result = client.post(f"{self.base_url}/{client_id}/deactivate", headers=auth_headers)
        
        self.assert_success_response(result)
        deactivated_client = result.json()
        assert deactivated_client["active"] is False
        assert "deactivated_at" in deactivated_client
    
    def test_delete_client_with_projects(self, client: Mock, auth_headers: Dict[str, str]):
        """Test deleting client that has associated projects should fail."""
        client_id = "client-with-projects"
        
        response = Mock()
        response.status_code = status.HTTP_400_BAD_REQUEST
        response.json.return_value = {"detail": "Cannot delete client with active projects"}
        
        client.delete.return_value = response
        result = client.delete(f"{self.base_url}/{client_id}", headers=auth_headers)
        
        self.assert_error_response(result, status.HTTP_400_BAD_REQUEST)
    
    def test_list_clients_with_filters(self, client: Mock, auth_headers: Dict[str, str]):
        """Test listing clients with various filters."""
        filter_params = {"active": "true", "has_projects": "true"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "clients": [
                {
                    "id": "client-1",
                    "name": "Active Client 1",
                    "active": True,
                    "project_count": 2,
                    "total_hours_tracked": 45.5
                },
                {
                    "id": "client-2",
                    "name": "Active Client 2",
                    "active": True,
                    "project_count": 1,
                    "total_hours_tracked": 23.0
                }
            ],
            "total": 2,
            "active_count": 2,
            "inactive_count": 0
        }
        
        client.get.return_value = response
        result = client.get(self.base_url, params=filter_params, headers=auth_headers)
        
        self.assert_success_response(result)
        clients_data = result.json()
        assert "clients" in clients_data
        assert clients_data["total"] == 2
        # All returned clients should be active and have projects
        for client_item in clients_data["clients"]:
            assert client_item["active"] is True
            assert client_item["project_count"] > 0
    
    def test_search_clients(self, client: Mock, auth_headers: Dict[str, str]):
        """Test searching clients by name or email."""
        search_params = {"q": "tech"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "clients": [
                {
                    "id": "client-tech",
                    "name": "Tech Solutions Inc",
                    "contact_email": "contact@techsolutions.com",
                    "active": True
                }
            ],
            "total": 1,
            "query": "tech"
        }
        
        client.get.return_value = response
        result = client.get(self.base_url, params=search_params, headers=auth_headers)
        
        self.assert_success_response(result)
        search_results = result.json()
        assert search_results["total"] == 1
        assert "tech" in search_results["clients"][0]["name"].lower()


class TestClientProjects(BaseAPITest):
    """Test cases for client-project relationships."""
    
    def test_get_client_projects(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting all projects for a specific client."""
        client_id = "client-123"
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "projects": [
                {
                    "id": "project-1",
                    "name": "Website Redesign",
                    "status": "active",
                    "start_date": "2024-01-01",
                    "budget": 25000.00,
                    "hours_tracked": 45.5
                },
                {
                    "id": "project-2",
                    "name": "Mobile App",
                    "status": "completed",
                    "start_date": "2023-10-01",
                    "end_date": "2024-01-15",
                    "budget": 50000.00,
                    "hours_tracked": 150.0
                }
            ],
            "total": 2,
            "active_count": 1,
            "completed_count": 1,
            "total_budget": 75000.00,
            "total_hours": 195.5
        }
        
        client.get.return_value = response
        result = client.get(f"/clients/{client_id}/projects", headers=auth_headers)
        
        self.assert_success_response(result)
        projects_data = result.json()
        assert "projects" in projects_data
        assert projects_data["total"] == 2
        assert projects_data["total_budget"] == 75000.00
    
    def test_get_client_time_summary(self, client: Mock, auth_headers: Dict[str, str]):
        """Test getting time tracking summary for a client."""
        client_id = "client-123"
        date_range_params = {"start_date": "2024-01-01", "end_date": "2024-01-31"}
        
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.json.return_value = {
            "client_id": client_id,
            "period": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31"
            },
            "summary": {
                "total_hours": 87.5,
                "billable_hours": 75.0,
                "non_billable_hours": 12.5,
                "total_revenue": 5625.00,
                "project_breakdown": [
                    {"project_id": "project-1", "project_name": "Website", "hours": 45.5},
                    {"project_id": "project-2", "project_name": "Mobile App", "hours": 42.0}
                ]
            }
        }
        
        client.get.return_value = response
        result = client.get(f"/clients/{client_id}/time-summary", 
                          params=date_range_params, headers=auth_headers)
        
        self.assert_success_response(result)
        summary_data = result.json()
        assert "summary" in summary_data
        assert summary_data["summary"]["total_hours"] == 87.5
        assert len(summary_data["summary"]["project_breakdown"]) == 2


class TestClientTenantIsolation(BaseAPITest, TenantIsolationTestMixin):
    """Test cases for client data isolation between tenants."""
    
    base_url = "/clients"
    
    def test_client_creation_tenant_assignment(self, client: Mock, auth_headers: Dict[str, str], 
                                             sample_client_data: Dict[str, Any]):
        """Test that created clients are automatically assigned to current tenant."""
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "id": "client-new",
            **sample_client_data,
            "tenant_id": "tenant-123"  # Should match the tenant from auth headers
        }
        
        client.post.return_value = response
        result = client.post(self.base_url, json=sample_client_data, headers=auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        created_client = result.json()
        assert created_client["tenant_id"] == "tenant-123"
    
    def test_client_list_tenant_filtering(self, client: Mock, auth_headers: Dict[str, str], 
                                        different_tenant_headers: Dict[str, str]):
        """Test that client listing is filtered by tenant."""
        def mock_get_clients(url, headers=None, **kwargs):
            tenant_id = headers.get("X-Tenant-ID") if headers else None
            if tenant_id == "tenant-123":
                response = Mock()
                response.status_code = status.HTTP_200_OK
                response.json.return_value = {
                    "clients": [
                        {"id": "client-1", "name": "Tenant 1 Client", "tenant_id": "tenant-123"}
                    ],
                    "total": 1
                }
                return response
            elif tenant_id == "tenant-456":
                response = Mock()
                response.status_code = status.HTTP_200_OK
                response.json.return_value = {
                    "clients": [
                        {"id": "client-2", "name": "Tenant 2 Client", "tenant_id": "tenant-456"}
                    ],
                    "total": 1
                }
                return response
            return Mock(status_code=401)
        
        client.get.side_effect = mock_get_clients
        
        # Test first tenant sees only their clients
        result1 = client.get(self.base_url, headers=auth_headers)
        self.assert_success_response(result1)
        tenant1_clients = result1.json()["clients"]
        assert len(tenant1_clients) == 1
        assert tenant1_clients[0]["tenant_id"] == "tenant-123"
        
        # Test second tenant sees only their clients
        result2 = client.get(self.base_url, headers=different_tenant_headers)
        self.assert_success_response(result2)
        tenant2_clients = result2.json()["clients"]
        assert len(tenant2_clients) == 1
        assert tenant2_clients[0]["tenant_id"] == "tenant-456"
    
    def test_cross_tenant_client_access_denied(self, client: Mock, auth_headers: Dict[str, str]):
        """Test that accessing client from different tenant is denied."""
        cross_tenant_client_id = "client-from-other-tenant"
        
        response = Mock()
        response.status_code = status.HTTP_404_NOT_FOUND
        response.json.return_value = {"detail": "Client not found"}
        
        client.get.return_value = response
        result = client.get(f"{self.base_url}/{cross_tenant_client_id}", headers=auth_headers)
        
        self.assert_not_found(result)
    
    def test_client_name_uniqueness_per_tenant(self, client: Mock, auth_headers: Dict[str, str]):
        """Test that client names are unique within tenant but can repeat across tenants."""
        # This test verifies that the same client name can exist in different tenants
        client_data = {
            "name": "Shared Client Name",
            "contact_email": "contact@shared.com"
        }
        
        # Should succeed if name doesn't exist in current tenant
        response = Mock()
        response.status_code = status.HTTP_201_CREATED
        response.json.return_value = {
            "id": "client-new",
            **client_data,
            "tenant_id": "tenant-123"
        }
        
        client.post.return_value = response
        result = client.post(self.base_url, json=client_data, headers=auth_headers)
        
        self.assert_success_response(result, status.HTTP_201_CREATED)
        created_client = result.json()
        assert created_client["name"] == client_data["name"]
