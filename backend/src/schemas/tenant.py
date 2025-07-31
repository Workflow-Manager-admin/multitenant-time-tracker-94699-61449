"""
Tenant-related Pydantic schemas.

Defines request/response models for tenant management, user invitations,
and tenant-specific operations.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID


class TenantCreateRequest(BaseModel):
    """Tenant creation request schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Tenant name")
    domain: Optional[str] = Field(None, max_length=255, description="Tenant domain")
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Tenant settings")


class TenantUpdateRequest(BaseModel):
    """Tenant update request schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Tenant name")
    domain: Optional[str] = Field(None, max_length=255, description="Tenant domain")
    settings: Optional[Dict[str, Any]] = Field(None, description="Tenant settings")


class TenantResponse(BaseModel):
    """Tenant response schema."""
    id: UUID = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    domain: Optional[str] = Field(None, description="Tenant domain")
    settings: Dict[str, Any] = Field(..., description="Tenant settings")
    active: bool = Field(..., description="Whether tenant is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    deactivated_at: Optional[datetime] = Field(None, description="Deactivation timestamp")
    user_count: Optional[int] = Field(None, description="Number of users in tenant")
    project_count: Optional[int] = Field(None, description="Number of projects in tenant")
    
    class Config:
        from_attributes = True


class TenantsListResponse(BaseModel):
    """Tenants list response schema."""
    tenants: List[TenantResponse] = Field(..., description="List of tenants")
    total: int = Field(..., description="Total number of tenants")
    active_count: int = Field(..., description="Number of active tenants")
    inactive_count: int = Field(..., description="Number of inactive tenants")


class UserInvitationRequest(BaseModel):
    """User invitation request schema."""
    email: EmailStr = Field(..., description="Email address to invite")
    role: str = Field(..., description="Role to assign to user")
    message: Optional[str] = Field(None, description="Custom invitation message")


class InvitationAcceptRequest(BaseModel):
    """Invitation acceptance request schema."""
    token: str = Field(..., description="Invitation token")
    password: str = Field(..., min_length=8, description="User password")
    first_name: str = Field(..., min_length=1, max_length=100, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User last name")


class InvitationResponse(BaseModel):
    """Invitation response schema."""
    id: UUID = Field(..., description="Invitation ID")
    email: EmailStr = Field(..., description="Invited email address")
    role: str = Field(..., description="Assigned role")
    tenant_id: UUID = Field(..., description="Tenant ID")
    status: str = Field(..., description="Invitation status")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True


class TenantUserResponse(BaseModel):
    """Tenant user response schema."""
    id: UUID = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    role: str = Field(..., description="User role")
    active: bool = Field(..., description="Whether user is active")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True


class TenantUsersResponse(BaseModel):
    """Tenant users response schema."""
    users: List[TenantUserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    active_count: int = Field(..., description="Number of active users")


class UserRoleUpdateRequest(BaseModel):
    """User role update request schema."""
    role: str = Field(..., description="New role for user")
