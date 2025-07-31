"""
User management-related Pydantic schemas.

Defines request/response models for user CRUD operations,
profile management, and user-specific operations.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID


class UserCreateRequest(BaseModel):
    """User creation request schema."""
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., min_length=1, max_length=100, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User last name")
    role: str = Field(..., description="User role")
    send_invitation: bool = Field(default=True, description="Whether to send invitation email")


class UserUpdateRequest(BaseModel):
    """User update request schema."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, description="User first name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, description="User last name")
    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences")


class UserResponse(BaseModel):
    """User response schema."""
    id: UUID = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    role: str = Field(..., description="User role")
    active: bool = Field(..., description="Whether user is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    deactivated_at: Optional[datetime] = Field(None, description="Deactivation timestamp")
    tenant_id: UUID = Field(..., description="Tenant ID")
    preferences: Dict[str, Any] = Field(..., description="User preferences")
    
    class Config:
        from_attributes = True


class UsersListResponse(BaseModel):
    """Users list response schema."""
    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    active_count: int = Field(..., description="Number of active users")
    admin_count: int = Field(..., description="Number of admin users")


class UserProfileResponse(BaseModel):
    """User profile response schema."""
    id: UUID = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    role: str = Field(..., description="User role")
    active: bool = Field(..., description="Whether user is active")
    preferences: Dict[str, Any] = Field(..., description="User preferences")
    
    class Config:
        from_attributes = True
