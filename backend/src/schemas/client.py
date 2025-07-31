"""
Client and project-related Pydantic schemas.

Defines request/response models for client management, project CRUD,
and related operations.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from decimal import Decimal


class ClientCreateRequest(BaseModel):
    """Client creation request schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Client name")
    contact_email: Optional[EmailStr] = Field(None, description="Client contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Client contact phone")
    address: Optional[str] = Field(None, description="Client address")


class ClientUpdateRequest(BaseModel):
    """Client update request schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Client name")
    contact_email: Optional[EmailStr] = Field(None, description="Client contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Client contact phone")
    address: Optional[str] = Field(None, description="Client address")
    active: Optional[bool] = Field(None, description="Whether client is active")


class ClientResponse(BaseModel):
    """Client response schema."""
    id: UUID = Field(..., description="Client ID")
    name: str = Field(..., description="Client name")
    contact_email: Optional[str] = Field(None, description="Client contact email")
    contact_phone: Optional[str] = Field(None, description="Client contact phone")
    address: Optional[str] = Field(None, description="Client address")
    active: bool = Field(..., description="Whether client is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    deactivated_at: Optional[datetime] = Field(None, description="Deactivation timestamp")
    tenant_id: UUID = Field(..., description="Tenant ID")
    project_count: Optional[int] = Field(None, description="Number of projects")
    total_hours_tracked: Optional[float] = Field(None, description="Total hours tracked")
    total_revenue: Optional[Decimal] = Field(None, description="Total revenue")
    
    class Config:
        from_attributes = True


class ClientsListResponse(BaseModel):
    """Clients list response schema."""
    clients: List[ClientResponse] = Field(..., description="List of clients")
    total: int = Field(..., description="Total number of clients")
    active_count: int = Field(..., description="Number of active clients")
    inactive_count: int = Field(..., description="Number of inactive clients")


class ProjectCreateRequest(BaseModel):
    """Project creation request schema."""
    client_id: UUID = Field(..., description="Client ID")
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date")
    budget: Optional[Decimal] = Field(None, ge=0, description="Project budget")
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Hourly rate")


class ProjectUpdateRequest(BaseModel):
    """Project update request schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: Optional[str] = Field(None, description="Project status")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date")
    budget: Optional[Decimal] = Field(None, ge=0, description="Project budget")
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Hourly rate")
    active: Optional[bool] = Field(None, description="Whether project is active")


class ProjectResponse(BaseModel):
    """Project response schema."""
    id: UUID = Field(..., description="Project ID")
    client_id: UUID = Field(..., description="Client ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: str = Field(..., description="Project status")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date")
    budget: Optional[Decimal] = Field(None, description="Project budget")
    hourly_rate: Optional[Decimal] = Field(None, description="Hourly rate")
    active: bool = Field(..., description="Whether project is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    tenant_id: UUID = Field(..., description="Tenant ID")
    hours_tracked: Optional[float] = Field(None, description="Total hours tracked")
    
    class Config:
        from_attributes = True


class ProjectsListResponse(BaseModel):
    """Projects list response schema."""
    projects: List[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")
    active_count: int = Field(..., description="Number of active projects")
    completed_count: int = Field(..., description="Number of completed projects")
    total_budget: Optional[Decimal] = Field(None, description="Total budget across projects")
    total_hours: Optional[float] = Field(None, description="Total hours across projects")


class ClientProjectsResponse(BaseModel):
    """Client projects response schema."""
    projects: List[ProjectResponse] = Field(..., description="List of projects for client")
    total: int = Field(..., description="Total number of projects")
    active_count: int = Field(..., description="Number of active projects")
    completed_count: int = Field(..., description="Number of completed projects")
    total_budget: Decimal = Field(..., description="Total budget across projects")
    total_hours: float = Field(..., description="Total hours across projects")


class ProjectBreakdown(BaseModel):
    """Project breakdown for time summary."""
    project_id: UUID = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project name")
    hours: float = Field(..., description="Hours worked on project")


class TimeSummaryResponse(BaseModel):
    """Time summary response schema."""
    client_id: UUID = Field(..., description="Client ID")
    period: dict = Field(..., description="Time period")
    summary: dict = Field(..., description="Summary data including hours and revenue")
