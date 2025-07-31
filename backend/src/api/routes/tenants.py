"""
Tenant management API routes.

Provides endpoints for tenant administration, user invitations,
and tenant-specific operations.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta

from ...database.connection import get_db
from ...database.models import Tenant, User, Invitation, UserRole
from ...schemas.tenant import (
    TenantCreateRequest, TenantUpdateRequest, TenantResponse,
    TenantsListResponse, UserInvitationRequest,
    InvitationResponse, TenantUserResponse, TenantUsersResponse,
    UserRoleUpdateRequest
)
from ...auth.dependencies import get_current_user, get_current_admin_user, CurrentUser
from ...auth.jwt_handler import JWTHandler

router = APIRouter(prefix="/tenants", tags=["Tenants"])


# PUBLIC_INTERFACE
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED,
            summary="Create new tenant",
            description="Create a new tenant (system admin only).")
async def create_tenant(
    request: TenantCreateRequest,
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Create a new tenant.
    
    Only system administrators can create new tenants.
    """
    # Check for duplicate name
    existing_tenant = db.query(Tenant).filter(Tenant.name == request.name).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant with this name already exists"
        )
    
    tenant = Tenant(
        id=uuid4(),
        name=request.name,
        domain=request.domain,
        settings=request.settings or {}
    )
    
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        domain=tenant.domain,
        settings=tenant.settings,
        active=tenant.active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        deactivated_at=tenant.deactivated_at,
        user_count=0,
        project_count=0
    )


# PUBLIC_INTERFACE
@router.get("/", response_model=TenantsListResponse,
           summary="List tenants",
           description="Get a list of all tenants (system admin only).")
async def list_tenants(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    List all tenants in the system.
    
    Only system administrators can access this endpoint.
    """
    query = db.query(Tenant)
    
    if active is not None:
        query = query.filter(Tenant.active == active)
    
    total = query.count()
    offset = (page - 1) * per_page
    tenants = query.offset(offset).limit(per_page).all()
    
    tenant_responses = []
    for tenant in tenants:
        user_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant.id).scalar() or 0
        # project_count would be calculated similarly
        
        tenant_responses.append(TenantResponse(
            id=tenant.id,
            name=tenant.name,
            domain=tenant.domain,
            settings=tenant.settings,
            active=tenant.active,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            deactivated_at=tenant.deactivated_at,
            user_count=user_count,
            project_count=0  # Placeholder
        ))
    
    active_count = db.query(func.count(Tenant.id)).filter(Tenant.active == True).scalar() or 0
    inactive_count = total - active_count
    
    return TenantsListResponse(
        tenants=tenant_responses,
        total=total,
        active_count=active_count,
        inactive_count=inactive_count
    )


# PUBLIC_INTERFACE
@router.get("/{tenant_id}", response_model=TenantResponse,
           summary="Get tenant details",
           description="Get detailed information about a specific tenant.")
async def get_tenant(
    tenant_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get tenant details.
    
    Users can view their own tenant, admins can view any tenant.
    """
    # Check permissions
    if tenant_id != current_user.tenant_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    user_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant.id).scalar() or 0
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        domain=tenant.domain,
        settings=tenant.settings,
        active=tenant.active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        deactivated_at=tenant.deactivated_at,
        user_count=user_count,
        project_count=0  # Placeholder
    )


# PUBLIC_INTERFACE
@router.put("/{tenant_id}", response_model=TenantResponse,
           summary="Update tenant",
           description="Update tenant information (admin only).")
async def update_tenant(
    tenant_id: UUID,
    request: TenantUpdateRequest,
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update tenant information.
    
    Only administrators can update tenant settings.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check for duplicate name if name is being updated
    if request.name and request.name != tenant.name:
        existing_tenant = db.query(Tenant).filter(
            Tenant.name == request.name,
            Tenant.id != tenant_id
        ).first()
        if existing_tenant:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tenant with this name already exists"
            )
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        domain=tenant.domain,
        settings=tenant.settings,
        active=tenant.active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        deactivated_at=tenant.deactivated_at,
        user_count=0,
        project_count=0
    )


# PUBLIC_INTERFACE
@router.post("/{tenant_id}/deactivate", response_model=TenantResponse,
            summary="Deactivate tenant",
            description="Deactivate a tenant (admin only).")
async def deactivate_tenant(
    tenant_id: UUID,
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate a tenant.
    
    Only administrators can deactivate tenants.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    tenant.active = False
    tenant.deactivated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(tenant)
    
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        domain=tenant.domain,
        settings=tenant.settings,
        active=tenant.active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        deactivated_at=tenant.deactivated_at,
        user_count=0,
        project_count=0
    )


# PUBLIC_INTERFACE
@router.post("/{tenant_id}/invite", response_model=InvitationResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Invite user to tenant",
            description="Send an invitation to join the tenant (admin only).")
async def invite_user_to_tenant(
    tenant_id: UUID,
    request: UserInvitationRequest,
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Invite a user to join the tenant.
    
    Only administrators can send invitations.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.active == True).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        User.email == request.email,
        User.tenant_id == tenant_id
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists in this tenant"
        )
    
    # Create invitation
    invitation_token = JWTHandler.create_invitation_token(
        request.email, tenant_id, request.role
    )
    
    invitation = Invitation(
        id=uuid4(),
        tenant_id=tenant_id,
        email=request.email,
        role=UserRole(request.role),
        token=invitation_token,
        message=request.message,
        invited_by_id=current_user.user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    # In real implementation, send invitation email
    
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role.value,
        tenant_id=invitation.tenant_id,
        status=invitation.status.value,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at
    )


# PUBLIC_INTERFACE
@router.get("/{tenant_id}/users", response_model=TenantUsersResponse,
           summary="List tenant users",
           description="Get a list of users in the tenant (admin only).")
async def list_tenant_users(
    tenant_id: UUID,
    active: Optional[bool] = Query(None, description="Filter by active status"),
    role: Optional[str] = Query(None, description="Filter by role"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    List users in the specified tenant.
    
    Only administrators can access this endpoint.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    query = db.query(User).filter(User.tenant_id == tenant_id)
    
    if active is not None:
        query = query.filter(User.active == active)
    
    if role:
        query = query.filter(User.role == UserRole(role))
    
    total = query.count()
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    user_responses = [
        TenantUserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            active=user.active,
            last_login=user.last_login,
            created_at=user.created_at
        )
        for user in users
    ]
    
    active_count = db.query(func.count(User.id)).filter(
        User.tenant_id == tenant_id,
        User.active == True
    ).scalar() or 0
    
    return TenantUsersResponse(
        users=user_responses,
        total=total,
        active_count=active_count
    )


# PUBLIC_INTERFACE
@router.put("/{tenant_id}/users/{user_id}/role", response_model=TenantUserResponse,
           summary="Update user role in tenant",
           description="Update a user's role within the tenant (admin only).")
async def update_user_role_in_tenant(
    tenant_id: UUID,
    user_id: UUID,
    request: UserRoleUpdateRequest,
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user role within the tenant.
    
    Only administrators can change user roles.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        user.role = UserRole(request.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid role"
        )
    
    db.commit()
    db.refresh(user)
    
    return TenantUserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        last_login=user.last_login,
        created_at=user.created_at
    )


# PUBLIC_INTERFACE
@router.delete("/{tenant_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
              summary="Remove user from tenant",
              description="Remove a user from the tenant (admin only).")
async def remove_user_from_tenant(
    tenant_id: UUID,
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Remove user from tenant.
    
    Only administrators can remove users from tenants.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # In a full implementation, you might want to deactivate instead of delete
    # or transfer ownership of resources
    db.delete(user)
    db.commit()
