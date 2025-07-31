"""
Authentication and user-related Pydantic schemas.

Defines request/response models for authentication, user registration,
login, password reset, and user management operations.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
from uuid import UUID


class UserRegistrationRequest(BaseModel):
    """User registration request schema."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")
    first_name: str = Field(..., min_length=1, max_length=100, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User last name")
    tenant_name: str = Field(..., min_length=1, max_length=255, description="Tenant name for new tenant")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('password too short')
        return v


class UserLoginRequest(BaseModel):
    """User login request schema."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""
    email: EmailStr = Field(..., description="User email address")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class TenantSelectionRequest(BaseModel):
    """Tenant selection request schema."""
    tenant_id: UUID = Field(..., description="Tenant ID to select")


class TenantInfo(BaseModel):
    """Tenant information schema."""
    id: UUID = Field(..., description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    role: str = Field(..., description="User role in this tenant")
    
    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    """User information schema."""
    id: UUID = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    role: str = Field(..., description="User role")
    active: bool = Field(..., description="Whether user is active")
    current_tenant_id: Optional[UUID] = Field(None, description="Currently selected tenant ID")
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User preferences")
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Authentication response schema."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: UserInfo = Field(..., description="User information")
    tenants: Optional[List[TenantInfo]] = Field(None, description="Available tenants")


class RegistrationResponse(BaseModel):
    """Registration response schema."""
    user: UserInfo = Field(..., description="Created user information")
    tenant: TenantInfo = Field(..., description="Created tenant information")
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class TokenRefreshResponse(BaseModel):
    """Token refresh response schema."""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class TenantSelectionResponse(BaseModel):
    """Tenant selection response schema."""
    message: str = Field(..., description="Success message")
    current_tenant: TenantInfo = Field(..., description="Selected tenant information")


class TenantsListResponse(BaseModel):
    """Tenants list response schema."""
    tenants: List[TenantInfo] = Field(..., description="Available tenants")


class UserActivityLog(BaseModel):
    """User activity log schema."""
    id: UUID = Field(..., description="Activity log ID")
    action: str = Field(..., description="Action performed")
    timestamp: datetime = Field(..., description="When the action occurred")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    details: Optional[str] = Field(None, description="Additional details")
    
    class Config:
        from_attributes = True


class UserActivityResponse(BaseModel):
    """User activity response schema."""
    activities: List[UserActivityLog] = Field(..., description="User activities")
    total: int = Field(..., description="Total number of activities")


class StandardResponse(BaseModel):
    """Standard API response schema."""
    message: str = Field(..., description="Response message")


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str = Field(..., description="Error detail message")
