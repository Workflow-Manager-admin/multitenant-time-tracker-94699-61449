"""
Project management API routes.

Provides endpoints for project CRUD operations, technology assignments,
and project-specific time tracking within tenant context.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID, uuid4

from ...database.connection import get_db
from ...database.models import Project, Client, TimeEntry, Technology, ProjectTechnology, ProjectStatus
from ...schemas.client import (
    ProjectCreateRequest, ProjectUpdateRequest, ProjectResponse,
    ProjectsListResponse
)
from ...schemas.time_tracking import TechnologyResponse
from ...auth.dependencies import get_current_user, get_tenant_filter, CurrentUser, TenantFilter

router = APIRouter(prefix="/projects", tags=["Projects"])


# PUBLIC_INTERFACE
@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED,
            summary="Create new project",
            description="Create a new project for a client within the current tenant.")
async def create_project(
    request: ProjectCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Create a new project.
    
    Creates a new project associated with a client in the current tenant.
    Project names must be unique within the client scope.
    """
    # Verify client exists and belongs to tenant
    client = db.query(Client).filter(
        Client.id == request.client_id,
        Client.tenant_id == tenant_filter.tenant_id,
        Client.active == True
    ).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check for duplicate name within client
    existing_project = db.query(Project).filter(
        Project.client_id == request.client_id,
        Project.name == request.name,
        Project.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if existing_project:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this name already exists for this client"
        )
    
    project = Project(
        id=uuid4(),
        tenant_id=tenant_filter.tenant_id,
        client_id=request.client_id,
        name=request.name,
        description=request.description,
        start_date=request.start_date,
        end_date=request.end_date,
        budget=request.budget,
        hourly_rate=request.hourly_rate
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return ProjectResponse(
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
        hours_tracked=0.0
    )


# PUBLIC_INTERFACE
@router.get("/", response_model=ProjectsListResponse,
           summary="List projects",
           description="Get a paginated list of projects with optional filtering.")
async def list_projects(
    client_id: Optional[UUID] = Query(None, description="Filter by client"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    status: Optional[str] = Query(None, description="Filter by project status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    List projects with filtering and pagination.
    
    Returns a paginated list of projects within the current tenant,
    with optional filtering by client, status, and other criteria.
    """
    query = db.query(Project).filter(Project.tenant_id == tenant_filter.tenant_id)
    
    # Apply filters
    if client_id:
        query = query.filter(Project.client_id == client_id)
    
    if active is not None:
        query = query.filter(Project.active == active)
    
    if status:
        try:
            project_status = ProjectStatus(status)
            query = query.filter(Project.status == project_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid project status"
            )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    projects = query.offset(offset).limit(per_page).all()
    
    # Build response with aggregated data
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
        
        if project.status == ProjectStatus.ACTIVE:
            active_count += 1
        elif project.status == ProjectStatus.COMPLETED:
            completed_count += 1
    
    return ProjectsListResponse(
        projects=project_responses,
        total=total,
        active_count=active_count,
        completed_count=completed_count,
        total_budget=total_budget,
        total_hours=total_hours
    )


# PUBLIC_INTERFACE
@router.get("/{project_id}", response_model=ProjectResponse,
           summary="Get project details",
           description="Get detailed information about a specific project.")
async def get_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Get project details.
    
    Returns detailed information about a specific project,
    including time tracking statistics and technology assignments.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Calculate hours tracked
    hours_result = db.query(func.sum(TimeEntry.duration_minutes)).filter(
        TimeEntry.project_id == project.id,
        TimeEntry.end_time.isnot(None)
    ).scalar()
    hours_tracked = (hours_result or 0) / 60.0
    
    return ProjectResponse(
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
    )


# PUBLIC_INTERFACE
@router.put("/{project_id}", response_model=ProjectResponse,
           summary="Update project",
           description="Update project information.")
async def update_project(
    project_id: UUID,
    request: ProjectUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Update project information.
    
    Updates the specified project with new information.
    Only provided fields will be updated.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Check for duplicate name if name is being updated
    if request.name and request.name != project.name:
        existing_project = db.query(Project).filter(
            Project.client_id == project.client_id,
            Project.name == request.name,
            Project.tenant_id == tenant_filter.tenant_id,
            Project.id != project_id
        ).first()
        
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project with this name already exists for this client"
            )
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value:
            try:
                setattr(project, field, ProjectStatus(value))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid project status"
                )
        else:
            setattr(project, field, value)
    
    db.commit()
    db.refresh(project)
    
    # Calculate hours tracked
    hours_result = db.query(func.sum(TimeEntry.duration_minutes)).filter(
        TimeEntry.project_id == project.id,
        TimeEntry.end_time.isnot(None)
    ).scalar()
    hours_tracked = (hours_result or 0) / 60.0
    
    return ProjectResponse(
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
    )


# PUBLIC_INTERFACE
@router.get("/{project_id}/technologies", response_model=List[TechnologyResponse],
           summary="Get project technologies",
           description="Get all technologies assigned to a project.")
async def get_project_technologies(
    project_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Get technologies assigned to a project.
    
    Returns all technologies that are associated with the specified project.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    technologies = db.query(Technology).join(ProjectTechnology).filter(
        ProjectTechnology.project_id == project_id
    ).all()
    
    return [TechnologyResponse.from_orm(tech) for tech in technologies]


# PUBLIC_INTERFACE
@router.post("/{project_id}/technologies/{technology_id}", status_code=status.HTTP_201_CREATED,
            summary="Assign technology to project",
            description="Assign a technology to a project.")
async def assign_technology_to_project(
    project_id: UUID,
    technology_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Assign a technology to a project.
    
    Creates an association between a project and a technology.
    """
    # Verify project exists
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Verify technology exists
    technology = db.query(Technology).filter(
        Technology.id == technology_id,
        Technology.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not technology:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Technology not found"
        )
    
    # Check if association already exists
    existing_assoc = db.query(ProjectTechnology).filter(
        ProjectTechnology.project_id == project_id,
        ProjectTechnology.technology_id == technology_id
    ).first()
    
    if existing_assoc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Technology is already assigned to this project"
        )
    
    # Create association
    project_tech = ProjectTechnology(
        id=uuid4(),
        project_id=project_id,
        technology_id=technology_id
    )
    
    db.add(project_tech)
    db.commit()
    
    return {"message": "Technology assigned to project successfully"}


# PUBLIC_INTERFACE
@router.delete("/{project_id}/technologies/{technology_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Remove technology from project",
              description="Remove a technology assignment from a project.")
async def remove_technology_from_project(
    project_id: UUID,
    technology_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Remove technology assignment from project.
    
    Removes the association between a project and a technology.
    """
    # Verify project exists
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Find and remove association
    project_tech = db.query(ProjectTechnology).filter(
        ProjectTechnology.project_id == project_id,
        ProjectTechnology.technology_id == technology_id
    ).first()
    
    if not project_tech:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Technology assignment not found"
        )
    
    db.delete(project_tech)
    db.commit()
