"""
Time tracking-related Pydantic schemas.

Defines request/response models for time entries, technologies,
and time tracking operations.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal


class TechnologyCreateRequest(BaseModel):
    """Technology creation request schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Technology name")
    category: Optional[str] = Field(None, max_length=100, description="Technology category")
    version: Optional[str] = Field(None, max_length=50, description="Technology version")
    description: Optional[str] = Field(None, description="Technology description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code")


class TechnologyUpdateRequest(BaseModel):
    """Technology update request schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Technology name")
    category: Optional[str] = Field(None, max_length=100, description="Technology category")
    version: Optional[str] = Field(None, max_length=50, description="Technology version")
    description: Optional[str] = Field(None, description="Technology description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code")
    active: Optional[bool] = Field(None, description="Whether technology is active")


class TechnologyResponse(BaseModel):
    """Technology response schema."""
    id: UUID = Field(..., description="Technology ID")
    name: str = Field(..., description="Technology name")
    category: Optional[str] = Field(None, description="Technology category")
    version: Optional[str] = Field(None, description="Technology version")
    description: Optional[str] = Field(None, description="Technology description")
    color: Optional[str] = Field(None, description="Hex color code")
    active: bool = Field(..., description="Whether technology is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    tenant_id: UUID = Field(..., description="Tenant ID")
    
    class Config:
        from_attributes = True


class TimeEntryCreateRequest(BaseModel):
    """Time entry creation request schema."""
    project_id: UUID = Field(..., description="Project ID")
    description: Optional[str] = Field(None, description="Work description")
    start_time: datetime = Field(..., description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time (null for running timer)")
    billable: bool = Field(default=True, description="Whether time is billable")
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Hourly rate")
    technology_ids: Optional[List[UUID]] = Field(default_factory=list, description="Associated technology IDs")


class TimeEntryUpdateRequest(BaseModel):
    """Time entry update request schema."""
    project_id: Optional[UUID] = Field(None, description="Project ID")
    description: Optional[str] = Field(None, description="Work description")
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    billable: Optional[bool] = Field(None, description="Whether time is billable")
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Hourly rate")
    technology_ids: Optional[List[UUID]] = Field(None, description="Associated technology IDs")


class TimeEntryResponse(BaseModel):
    """Time entry response schema."""
    id: UUID = Field(..., description="Time entry ID")
    project_id: UUID = Field(..., description="Project ID")
    user_id: UUID = Field(..., description="User ID")
    description: Optional[str] = Field(None, description="Work description")
    start_time: datetime = Field(..., description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes")
    billable: bool = Field(..., description="Whether time is billable")
    hourly_rate: Optional[Decimal] = Field(None, description="Hourly rate")
    amount: Optional[Decimal] = Field(None, description="Calculated amount")
    is_running: bool = Field(..., description="Whether timer is currently running")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    tenant_id: UUID = Field(..., description="Tenant ID")
    technologies: Optional[List[TechnologyResponse]] = Field(default_factory=list, description="Associated technologies")
    
    class Config:
        from_attributes = True


class TimerStartRequest(BaseModel):
    """Timer start request schema."""
    project_id: UUID = Field(..., description="Project ID")
    description: Optional[str] = Field(None, description="Work description")
    technology_ids: Optional[List[UUID]] = Field(default_factory=list, description="Associated technology IDs")


class TimerStopRequest(BaseModel):
    """Timer stop request schema."""
    description: Optional[str] = Field(None, description="Final work description")


class TimeEntriesListResponse(BaseModel):
    """Time entries list response schema."""
    entries: List[TimeEntryResponse] = Field(..., description="List of time entries")
    total: int = Field(..., description="Total number of entries")
    total_hours: float = Field(..., description="Total hours")
    billable_hours: float = Field(..., description="Total billable hours")
    total_amount: Decimal = Field(..., description="Total amount")


class DashboardSummary(BaseModel):
    """Dashboard summary response schema."""
    today_hours: float = Field(..., description="Hours worked today")
    week_hours: float = Field(..., description="Hours worked this week")
    month_hours: float = Field(..., description="Hours worked this month")
    running_timer: Optional[TimeEntryResponse] = Field(None, description="Currently running timer")
    recent_entries: List[TimeEntryResponse] = Field(..., description="Recent time entries")
    project_breakdown: List[dict] = Field(..., description="Breakdown by project")
    client_breakdown: List[dict] = Field(..., description="Breakdown by client")
    technology_breakdown: List[dict] = Field(..., description="Breakdown by technology")


class ReportRequest(BaseModel):
    """Report generation request schema."""
    start_date: datetime = Field(..., description="Report start date")
    end_date: datetime = Field(..., description="Report end date")
    project_ids: Optional[List[UUID]] = Field(None, description="Filter by project IDs")
    client_ids: Optional[List[UUID]] = Field(None, description="Filter by client IDs")
    user_ids: Optional[List[UUID]] = Field(None, description="Filter by user IDs")
    billable_only: Optional[bool] = Field(None, description="Include only billable entries")
    format: str = Field(default="json", description="Report format (json, csv, pdf)")


class ReportResponse(BaseModel):
    """Report response schema."""
    period: dict = Field(..., description="Report period")
    summary: dict = Field(..., description="Summary statistics")
    entries: List[TimeEntryResponse] = Field(..., description="Time entries")
    breakdown: dict = Field(..., description="Various breakdowns")
