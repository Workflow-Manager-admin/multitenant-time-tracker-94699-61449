"""
Client management API routes.

Provides endpoints for client CRUD operations, project management,
and client-specific reporting within tenant context.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID, uuid4

from ...database.connection import get_db
from ...database.models import Client, Project, TimeEntry
from ...schemas.client import (
    ClientCreateRequest, ClientUpdateRequest, ClientResponse,
    ClientsListResponse, ClientProjectsResponse,
    TimeSummaryResponse, ProjectResponse
)
from ...auth.dependencies import get_current_user, get_tenant_filter, CurrentUser, TenantFilter

router = APIRouter(prefix="/clients", tags=["Clients"])


# PUBLIC_INTERFACE
@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED,
            summary="Create new client",
            description="Create a new client within the current tenant context.")
async def create_client(
    request: ClientCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Create a new client.
    
    Creates a new client associated with the current tenant.
    Client names must be unique within the tenant.
    """
    # Check for duplicate name within tenant
    existing_client = db.query(Client).filter(
        Client.tenant_id == tenant_filter.tenant_id,
        Client.name == request.name
    ).first()
    
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client with this name already exists in this tenant"
        )
    
    # Create client
    client = Client(
        id=uuid4(),
        tenant_id=tenant_filter.tenant_id,
        name=request.name,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        address=request.address
    )
    
    db.add(client)
    db.commit()
    db.refresh(client)
    
    return ClientResponse(
        id=client.id,
        name=client.name,
        contact_email=client.contact_email,
        contact_phone=client.contact_phone,
        address=client.address,
        active=client.active,
        created_at=client.created_at,
        updated_at=client.updated_at,
        deactivated_at=client.deactivated_at,
        tenant_id=client.tenant_id,
        project_count=0,
        total_hours_tracked=0.0,
        total_revenue=0.0
    )


# PUBLIC_INTERFACE
@router.get("/", response_model=ClientsListResponse,
           summary="List clients",
           description="Get a paginated list of clients with optional filtering.")
async def list_clients(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    has_projects: Optional[bool] = Query(None, description="Filter clients with/without projects"),
    q: Optional[str] = Query(None, description="Search query for name or email"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    List clients with filtering and pagination.
    
    Returns a paginated list of clients within the current tenant,
    with optional filtering by status and search capabilities.
    """
    query = db.query(Client).filter(Client.tenant_id == tenant_filter.tenant_id)
    
    # Apply filters
    if active is not None:
        query = query.filter(Client.active == active)
    
    if q:
        query = query.filter(
            (Client.name.ilike(f"%{q}%")) |
            (Client.contact_email.ilike(f"%{q}%"))
        )
    
    # Join with projects for has_projects filter
    if has_projects is not None:
        if has_projects:
            query = query.join(Project).filter(Project.active == True)
        else:
            query = query.outerjoin(Project).filter(Project.id.is_(None))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    clients = query.offset(offset).limit(per_page).all()
    
    # Get aggregated data for each client
    client_responses = []
    for client in clients:
        # Count projects
        project_count = db.query(func.count(Project.id)).filter(
            Project.client_id == client.id,
            Project.active == True
        ).scalar() or 0
        
        # Get total hours and revenue
        time_stats = db.query(
            func.sum(TimeEntry.duration_minutes),
            func.sum(TimeEntry.amount)
        ).join(Project).filter(
            Project.client_id == client.id,
            TimeEntry.end_time.isnot(None)
        ).first()
        
        total_hours = (time_stats[0] or 0) / 60.0  # Convert minutes to hours
        total_revenue = time_stats[1] or 0.0
        
        client_responses.append(ClientResponse(
            id=client.id,
            name=client.name,
            contact_email=client.contact_email,
            contact_phone=client.contact_phone,
            address=client.address,
            active=client.active,
            created_at=client.created_at,
            updated_at=client.updated_at,
            deactivated_at=client.deactivated_at,
            tenant_id=client.tenant_id,
            project_count=project_count,
            total_hours_tracked=total_hours,
            total_revenue=total_revenue
        ))
    
    # Count active/inactive
    active_count = db.query(func.count(Client.id)).filter(
        Client.tenant_id == tenant_filter.tenant_id,
        Client.active == True
    ).scalar() or 0
    
    inactive_count = total - active_count
    
    return ClientsListResponse(
        clients=client_responses,
        total=total,
        active_count=active_count,
        inactive_count=inactive_count
    )


# PUBLIC_INTERFACE
@router.get("/{client_id}", response_model=ClientResponse,
           summary="Get client details",
           description="Get detailed information about a specific client.")
async def get_client(
    client_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Get client details.
    
    Returns detailed information about a specific client,
    including project count and time tracking statistics.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Get aggregated data
    project_count = db.query(func.count(Project.id)).filter(
        Project.client_id == client.id,
        Project.active == True
    ).scalar() or 0
    
    time_stats = db.query(
        func.sum(TimeEntry.duration_minutes),
        func.sum(TimeEntry.amount)
    ).join(Project).filter(
        Project.client_id == client.id,
        TimeEntry.end_time.isnot(None)
    ).first()
    
    total_hours = (time_stats[0] or 0) / 60.0
    total_revenue = time_stats[1] or 0.0
    
    return ClientResponse(
        id=client.id,
        name=client.name,
        contact_email=client.contact_email,
        contact_phone=client.contact_phone,
        address=client.address,
        active=client.active,
        created_at=client.created_at,
        updated_at=client.updated_at,
        deactivated_at=client.deactivated_at,
        tenant_id=client.tenant_id,
        project_count=project_count,
        total_hours_tracked=total_hours,
        total_revenue=total_revenue
    )


# PUBLIC_INTERFACE
@router.put("/{client_id}", response_model=ClientResponse,
           summary="Update client",
           description="Update client information.")
async def update_client(
    client_id: UUID,
    request: ClientUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Update client information.
    
    Updates the specified client with new information.
    Only provided fields will be updated.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check for duplicate name if name is being updated
    if request.name and request.name != client.name:
        existing_client = db.query(Client).filter(
            Client.tenant_id == tenant_filter.tenant_id,
            Client.name == request.name,
            Client.id != client_id
        ).first()
        
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client with this name already exists in this tenant"
            )
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    
    db.commit()
    db.refresh(client)
    
    # Get current stats
    project_count = db.query(func.count(Project.id)).filter(
        Project.client_id == client.id,
        Project.active == True
    ).scalar() or 0
    
    return ClientResponse(
        id=client.id,
        name=client.name,
        contact_email=client.contact_email,
        contact_phone=client.contact_phone,
        address=client.address,
        active=client.active,
        created_at=client.created_at,
        updated_at=client.updated_at,
        deactivated_at=client.deactivated_at,
        tenant_id=client.tenant_id,
        project_count=project_count,
        total_hours_tracked=0.0,  # Would calculate in real implementation
        total_revenue=0.0
    )


# PUBLIC_INTERFACE
@router.post("/{client_id}/deactivate", response_model=ClientResponse,
            summary="Deactivate client",
            description="Deactivate a client account.")
async def deactivate_client(
    client_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Deactivate a client.
    
    Marks the client as inactive. The client will no longer appear
    in active client lists but historical data is preserved.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    client.active = False
    from datetime import datetime, timezone
    client.deactivated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(client)
    
    return ClientResponse(
        id=client.id,
        name=client.name,
        contact_email=client.contact_email,
        contact_phone=client.contact_phone,
        address=client.address,
        active=client.active,
        created_at=client.created_at,
        updated_at=client.updated_at,
        deactivated_at=client.deactivated_at,
        tenant_id=client.tenant_id,
        project_count=0,
        total_hours_tracked=0.0,
        total_revenue=0.0
    )


# PUBLIC_INTERFACE
@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Delete client",
              description="Delete a client if they have no associated projects.")
async def delete_client(
    client_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Delete a client.
    
    Permanently deletes a client if they have no associated projects.
    If the client has projects, deactivate instead of delete.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check for associated projects
    project_count = db.query(func.count(Project.id)).filter(
        Project.client_id == client_id
    ).scalar()
    
    if project_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete client with active projects"
        )
    
    db.delete(client)
    db.commit()


# PUBLIC_INTERFACE
@router.get("/{client_id}/projects", response_model=ClientProjectsResponse,
           summary="Get client projects",
           description="Get all projects for a specific client.")
async def get_client_projects(
    client_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Get all projects for a client.
    
    Returns all projects associated with the specified client,
    including project statistics and status information.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    projects = db.query(Project).filter(Project.client_id == client_id).all()
    
    project_responses = []
    total_budget = 0.0
    total_hours = 0.0
    active_count = 0
    completed_count = 0
    
    for project in projects:
        # Calculate hours tracked
        hours_result = db.query(func.sum(TimeEntry.duration_minutes)).filter(
            TimeEntry.project_id == project.id,
            TimeEntry.end_time.isnot(None)
        ).scalar()
        hours_tracked = (hours_result or 0) / 60.0
        
        project_responses.append(ProjectResponse(
            id=project.id,
            client_id=project.client_id,
            name=project.name,
            description=project.description,
            status=project.status.value,
            start_date=project.start_date,
            end_date=project.end_date,
            budget=project.budget,
            hourly_rate=project.hourly_rate,
            active=project.active,
            created_at=project.created_at,
            updated_at=project.updated_at,
            tenant_id=project.tenant_id,
            hours_tracked=hours_tracked
        ))
        
        if project.budget:
            total_budget += float(project.budget)
        total_hours += hours_tracked
        
        if project.status.value == "active":
            active_count += 1
        elif project.status.value == "completed":
            completed_count += 1
    
    return ClientProjectsResponse(
        projects=project_responses,
        total=len(projects),
        active_count=active_count,
        completed_count=completed_count,
        total_budget=total_budget,
        total_hours=total_hours
    )


# PUBLIC_INTERFACE
@router.get("/{client_id}/time-summary", response_model=TimeSummaryResponse,
           summary="Get client time summary",
           description="Get time tracking summary for a client within a date range.")
async def get_client_time_summary(
    client_id: UUID,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Get time tracking summary for a client.
    
    Returns detailed time tracking statistics for the specified client
    within the given date range, including breakdowns by project.
    """
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Parse dates
    from datetime import datetime
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )
    
    # Get time entries for the period
    time_entries = db.query(TimeEntry).join(Project).filter(
        Project.client_id == client_id,
        TimeEntry.start_time >= start_dt,
        TimeEntry.start_time <= end_dt,
        TimeEntry.end_time.isnot(None)
    ).all()
    
    total_hours = sum((entry.duration_minutes or 0) / 60.0 for entry in time_entries)
    billable_hours = sum((entry.duration_minutes or 0) / 60.0 for entry in time_entries if entry.billable)
    non_billable_hours = total_hours - billable_hours
    total_revenue = sum(float(entry.amount or 0) for entry in time_entries)
    
    # Project breakdown
    project_breakdown = {}
    for entry in time_entries:
        project_id = str(entry.project_id)
        if project_id not in project_breakdown:
            project = db.query(Project).filter(Project.id == entry.project_id).first()
            project_breakdown[project_id] = {
                "project_id": project_id,
                "project_name": project.name if project else "Unknown",
                "hours": 0.0
            }
        project_breakdown[project_id]["hours"] += (entry.duration_minutes or 0) / 60.0
    
    return TimeSummaryResponse(
        client_id=client_id,
        period={
            "start_date": start_date,
            "end_date": end_date
        },
        summary={
            "total_hours": total_hours,
            "billable_hours": billable_hours,
            "non_billable_hours": non_billable_hours,
            "total_revenue": total_revenue,
            "project_breakdown": list(project_breakdown.values())
        }
    )
