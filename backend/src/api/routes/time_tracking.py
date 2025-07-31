"""
Time tracking API routes.

Provides endpoints for time entries, technologies, timers,
and reporting functionality.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from ...database.connection import get_db
from ...database.models import (
    TimeEntry, Technology, Project, TimeEntryTechnology
)
from ...schemas.time_tracking import (
    TechnologyCreateRequest, TechnologyResponse,
    TimeEntryCreateRequest, TimeEntryResponse,
    TimerStartRequest, TimerStopRequest, TimeEntriesListResponse,
    DashboardSummary
)
from ...auth.dependencies import get_current_user, get_tenant_filter, CurrentUser, TenantFilter

router = APIRouter(tags=["Time Tracking"])


# Technology Management Routes
technology_router = APIRouter(prefix="/technologies", tags=["Technologies"])


# PUBLIC_INTERFACE
@technology_router.post("/", response_model=TechnologyResponse, status_code=status.HTTP_201_CREATED,
                       summary="Create new technology",
                       description="Create a new technology for categorizing work.")
async def create_technology(
    request: TechnologyCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Create a new technology.
    
    Technologies are used to categorize and tag time entries and projects.
    """
    # Check for duplicate name within tenant
    existing_tech = db.query(Technology).filter(
        Technology.tenant_id == tenant_filter.tenant_id,
        Technology.name == request.name
    ).first()
    
    if existing_tech:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Technology with this name already exists in this tenant"
        )
    
    technology = Technology(
        id=uuid4(),
        tenant_id=tenant_filter.tenant_id,
        name=request.name,
        category=request.category,
        version=request.version,
        description=request.description,
        color=request.color
    )
    
    db.add(technology)
    db.commit()
    db.refresh(technology)
    
    return TechnologyResponse.from_orm(technology)


# PUBLIC_INTERFACE
@technology_router.get("/", response_model=List[TechnologyResponse],
                      summary="List technologies",
                      description="Get a list of all technologies in the tenant.")
async def list_technologies(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    List technologies in the current tenant.
    
    Returns all technologies available for time tracking and project assignment.
    """
    query = db.query(Technology).filter(Technology.tenant_id == tenant_filter.tenant_id)
    
    if active is not None:
        query = query.filter(Technology.active == active)
    
    if category:
        query = query.filter(Technology.category == category)
    
    technologies = query.all()
    return [TechnologyResponse.from_orm(tech) for tech in technologies]


# Time Entry Management Routes
time_entries_router = APIRouter(prefix="/time-entries", tags=["Time Entries"])


# PUBLIC_INTERFACE
@time_entries_router.post("/", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED,
                         summary="Create time entry",
                         description="Create a new time entry for tracking work.")
async def create_time_entry(
    request: TimeEntryCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Create a new time entry.
    
    Creates a time entry for the current user. If end_time is not provided,
    it creates a running timer.
    """
    # Verify project exists and belongs to tenant
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.tenant_id == tenant_filter.tenant_id,
        Project.active == True
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check if user already has a running timer
    if request.end_time is None:
        running_timer = db.query(TimeEntry).filter(
            TimeEntry.user_id == current_user.user_id,
            TimeEntry.tenant_id == tenant_filter.tenant_id,
            TimeEntry.is_running == True
        ).first()
        
        if running_timer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a running timer. Stop it before starting a new one."
            )
    
    # Calculate duration and amount if end_time provided
    duration_minutes = None
    amount = None
    is_running = request.end_time is None
    
    if request.end_time:
        duration = request.end_time - request.start_time
        duration_minutes = int(duration.total_seconds() / 60)
        
        if request.hourly_rate and duration_minutes:
            amount = (Decimal(str(request.hourly_rate)) * Decimal(str(duration_minutes))) / Decimal('60')
    
    time_entry = TimeEntry(
        id=uuid4(),
        tenant_id=tenant_filter.tenant_id,
        user_id=current_user.user_id,
        project_id=request.project_id,
        description=request.description,
        start_time=request.start_time,
        end_time=request.end_time,
        duration_minutes=duration_minutes,
        billable=request.billable,
        hourly_rate=request.hourly_rate,
        amount=amount,
        is_running=is_running
    )
    
    db.add(time_entry)
    db.flush()
    
    # Add technology associations
    if request.technology_ids:
        for tech_id in request.technology_ids:
            # Verify technology exists and belongs to tenant
            tech = db.query(Technology).filter(
                Technology.id == tech_id,
                Technology.tenant_id == tenant_filter.tenant_id
            ).first()
            
            if tech:
                tech_assoc = TimeEntryTechnology(
                    id=uuid4(),
                    time_entry_id=time_entry.id,
                    technology_id=tech_id
                )
                db.add(tech_assoc)
    
    db.commit()
    db.refresh(time_entry)
    
    # Load technologies for response
    technologies = db.query(Technology).join(TimeEntryTechnology).filter(
        TimeEntryTechnology.time_entry_id == time_entry.id
    ).all()
    
    return TimeEntryResponse(
        id=time_entry.id,
        project_id=time_entry.project_id,
        user_id=time_entry.user_id,
        description=time_entry.description,
        start_time=time_entry.start_time,
        end_time=time_entry.end_time,
        duration_minutes=time_entry.duration_minutes,
        billable=time_entry.billable,
        hourly_rate=time_entry.hourly_rate,
        amount=time_entry.amount,
        is_running=time_entry.is_running,
        created_at=time_entry.created_at,
        updated_at=time_entry.updated_at,
        tenant_id=time_entry.tenant_id,
        technologies=[TechnologyResponse.from_orm(tech) for tech in technologies]
    )


# PUBLIC_INTERFACE
@time_entries_router.get("/", response_model=TimeEntriesListResponse,
                        summary="List time entries",
                        description="Get a paginated list of time entries with filtering.")
async def list_time_entries(
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    billable: Optional[bool] = Query(None, description="Filter by billable status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    List time entries with filtering and pagination.
    
    Returns time entries for the current user with various filtering options.
    """
    query = db.query(TimeEntry).filter(
        TimeEntry.user_id == current_user.user_id,
        TimeEntry.tenant_id == tenant_filter.tenant_id
    ).order_by(desc(TimeEntry.start_time))
    
    # Apply filters
    if project_id:
        query = query.filter(TimeEntry.project_id == project_id)
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(TimeEntry.start_time >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD."
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(TimeEntry.start_time <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD."
            )
    
    if billable is not None:
        query = query.filter(TimeEntry.billable == billable)
    
    # Get statistics
    total = query.count()
    
    # Calculate totals
    stats_query = query.filter(TimeEntry.end_time.isnot(None))
    total_minutes = stats_query.with_entities(func.sum(TimeEntry.duration_minutes)).scalar() or 0
    billable_minutes = stats_query.filter(TimeEntry.billable == True).with_entities(func.sum(TimeEntry.duration_minutes)).scalar() or 0
    total_amount = stats_query.with_entities(func.sum(TimeEntry.amount)).scalar() or Decimal('0')
    
    # Apply pagination
    offset = (page - 1) * per_page
    entries = query.offset(offset).limit(per_page).all()
    
    # Build response entries with technologies
    entry_responses = []
    for entry in entries:
        technologies = db.query(Technology).join(TimeEntryTechnology).filter(
            TimeEntryTechnology.time_entry_id == entry.id
        ).all()
        
        entry_responses.append(TimeEntryResponse(
            id=entry.id,
            project_id=entry.project_id,
            user_id=entry.user_id,
            description=entry.description,
            start_time=entry.start_time,
            end_time=entry.end_time,
            duration_minutes=entry.duration_minutes,
            billable=entry.billable,
            hourly_rate=entry.hourly_rate,
            amount=entry.amount,
            is_running=entry.is_running,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            tenant_id=entry.tenant_id,
            technologies=[TechnologyResponse.from_orm(tech) for tech in technologies]
        ))
    
    return TimeEntriesListResponse(
        entries=entry_responses,
        total=total,
        total_hours=float(total_minutes) / 60.0,
        billable_hours=float(billable_minutes) / 60.0,
        total_amount=total_amount
    )


# Timer Management Routes
timer_router = APIRouter(prefix="/timer", tags=["Timer"])


# PUBLIC_INTERFACE
@timer_router.post("/start", response_model=TimeEntryResponse,
                  summary="Start timer",
                  description="Start a new work timer.")
async def start_timer(
    request: TimerStartRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Start a new timer.
    
    Creates a running time entry that can be stopped later.
    """
    # Check if user already has a running timer
    running_timer = db.query(TimeEntry).filter(
        TimeEntry.user_id == current_user.user_id,
        TimeEntry.tenant_id == tenant_filter.tenant_id,
        TimeEntry.is_running == True
    ).first()
    
    if running_timer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a running timer. Stop it before starting a new one."
        )
    
    # Verify project exists
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.tenant_id == tenant_filter.tenant_id,
        Project.active == True
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Create time entry
    time_entry = TimeEntry(
        id=uuid4(),
        tenant_id=tenant_filter.tenant_id,
        user_id=current_user.user_id,
        project_id=request.project_id,
        description=request.description,
        start_time=datetime.now(timezone.utc),
        is_running=True,
        billable=True  # Default to billable
    )
    
    db.add(time_entry)
    db.flush()
    
    # Add technology associations
    if request.technology_ids:
        for tech_id in request.technology_ids:
            tech = db.query(Technology).filter(
                Technology.id == tech_id,
                Technology.tenant_id == tenant_filter.tenant_id
            ).first()
            
            if tech:
                tech_assoc = TimeEntryTechnology(
                    id=uuid4(),
                    time_entry_id=time_entry.id,
                    technology_id=tech_id
                )
                db.add(tech_assoc)
    
    db.commit()
    db.refresh(time_entry)
    
    # Load technologies for response
    technologies = db.query(Technology).join(TimeEntryTechnology).filter(
        TimeEntryTechnology.time_entry_id == time_entry.id
    ).all()
    
    return TimeEntryResponse(
        id=time_entry.id,
        project_id=time_entry.project_id,
        user_id=time_entry.user_id,
        description=time_entry.description,
        start_time=time_entry.start_time,
        end_time=time_entry.end_time,
        duration_minutes=time_entry.duration_minutes,
        billable=time_entry.billable,
        hourly_rate=time_entry.hourly_rate,
        amount=time_entry.amount,
        is_running=time_entry.is_running,
        created_at=time_entry.created_at,
        updated_at=time_entry.updated_at,
        tenant_id=time_entry.tenant_id,
        technologies=[TechnologyResponse.from_orm(tech) for tech in technologies]
    )


# PUBLIC_INTERFACE
@timer_router.post("/stop", response_model=TimeEntryResponse,
                  summary="Stop timer",
                  description="Stop the currently running timer.")
async def stop_timer(
    request: TimerStopRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Stop the currently running timer.
    
    Stops the active timer and calculates final duration and amount.
    """
    # Find running timer
    running_timer = db.query(TimeEntry).filter(
        TimeEntry.user_id == current_user.user_id,
        TimeEntry.tenant_id == tenant_filter.tenant_id,
        TimeEntry.is_running == True
    ).first()
    
    if not running_timer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No running timer found"
        )
    
    # Stop timer
    end_time = datetime.now(timezone.utc)
    duration = end_time - running_timer.start_time
    duration_minutes = int(duration.total_seconds() / 60)
    
    running_timer.end_time = end_time
    running_timer.duration_minutes = duration_minutes
    running_timer.is_running = False
    
    # Update description if provided
    if request.description:
        running_timer.description = request.description
    
    # Calculate amount if hourly rate is set
    if running_timer.hourly_rate:
        running_timer.amount = (Decimal(str(running_timer.hourly_rate)) * Decimal(str(duration_minutes))) / Decimal('60')
    
    db.commit()
    db.refresh(running_timer)
    
    # Load technologies for response
    technologies = db.query(Technology).join(TimeEntryTechnology).filter(
        TimeEntryTechnology.time_entry_id == running_timer.id
    ).all()
    
    return TimeEntryResponse(
        id=running_timer.id,
        project_id=running_timer.project_id,
        user_id=running_timer.user_id,
        description=running_timer.description,
        start_time=running_timer.start_time,
        end_time=running_timer.end_time,
        duration_minutes=running_timer.duration_minutes,
        billable=running_timer.billable,
        hourly_rate=running_timer.hourly_rate,
        amount=running_timer.amount,
        is_running=running_timer.is_running,
        created_at=running_timer.created_at,
        updated_at=running_timer.updated_at,
        tenant_id=running_timer.tenant_id,
        technologies=[TechnologyResponse.from_orm(tech) for tech in technologies]
    )


# Dashboard Route
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# PUBLIC_INTERFACE
@dashboard_router.get("/", response_model=DashboardSummary,
                     summary="Get dashboard summary",
                     description="Get time tracking summary for dashboard display.")
async def get_dashboard_summary(
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Get dashboard summary data.
    
    Returns time tracking statistics and summaries for the current user.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    # Get running timer
    running_timer = db.query(TimeEntry).filter(
        TimeEntry.user_id == current_user.user_id,
        TimeEntry.tenant_id == tenant_filter.tenant_id,
        TimeEntry.is_running == True
    ).first()
    
    running_timer_response = None
    if running_timer:
        technologies = db.query(Technology).join(TimeEntryTechnology).filter(
            TimeEntryTechnology.time_entry_id == running_timer.id
        ).all()
        
        running_timer_response = TimeEntryResponse(
            id=running_timer.id,
            project_id=running_timer.project_id,
            user_id=running_timer.user_id,
            description=running_timer.description,
            start_time=running_timer.start_time,
            end_time=running_timer.end_time,
            duration_minutes=running_timer.duration_minutes,
            billable=running_timer.billable,
            hourly_rate=running_timer.hourly_rate,
            amount=running_timer.amount,
            is_running=running_timer.is_running,
            created_at=running_timer.created_at,
            updated_at=running_timer.updated_at,
            tenant_id=running_timer.tenant_id,
            technologies=[TechnologyResponse.from_orm(tech) for tech in technologies]
        )
    
    # Calculate time summaries
    def get_hours_for_period(start_date):
        result = db.query(func.sum(TimeEntry.duration_minutes)).filter(
            TimeEntry.user_id == current_user.user_id,
            TimeEntry.tenant_id == tenant_filter.tenant_id,
            TimeEntry.start_time >= start_date,
            TimeEntry.end_time.isnot(None)
        ).scalar()
        return float(result or 0) / 60.0
    
    today_hours = get_hours_for_period(today_start)
    week_hours = get_hours_for_period(week_start)
    month_hours = get_hours_for_period(month_start)
    
    # Get recent entries
    recent_entries = db.query(TimeEntry).filter(
        TimeEntry.user_id == current_user.user_id,
        TimeEntry.tenant_id == tenant_filter.tenant_id,
        TimeEntry.end_time.isnot(None)
    ).order_by(desc(TimeEntry.start_time)).limit(5).all()
    
    recent_entry_responses = []
    for entry in recent_entries:
        technologies = db.query(Technology).join(TimeEntryTechnology).filter(
            TimeEntryTechnology.time_entry_id == entry.id
        ).all()
        
        recent_entry_responses.append(TimeEntryResponse(
            id=entry.id,
            project_id=entry.project_id,
            user_id=entry.user_id,
            description=entry.description,
            start_time=entry.start_time,
            end_time=entry.end_time,
            duration_minutes=entry.duration_minutes,
            billable=entry.billable,
            hourly_rate=entry.hourly_rate,
            amount=entry.amount,
            is_running=entry.is_running,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            tenant_id=entry.tenant_id,
            technologies=[TechnologyResponse.from_orm(tech) for tech in technologies]
        ))
    
    return DashboardSummary(
        today_hours=today_hours,
        week_hours=week_hours,
        month_hours=month_hours,
        running_timer=running_timer_response,
        recent_entries=recent_entry_responses,
        project_breakdown=[],  # Placeholder - would calculate project breakdown
        client_breakdown=[],   # Placeholder - would calculate client breakdown
        technology_breakdown=[]  # Placeholder - would calculate technology breakdown
    )


# Include sub-routers
router.include_router(technology_router)
router.include_router(time_entries_router)
router.include_router(timer_router)
router.include_router(dashboard_router)
