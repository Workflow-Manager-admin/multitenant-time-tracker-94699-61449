"""
User management API routes.

Provides endpoints for user CRUD operations, profile management,
and user-specific operations within tenant context.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID, uuid4

from ...database.connection import get_db
from ...database.models import User, UserActivityLog, UserRole
from ...schemas.user import (
    UserCreateRequest, UserUpdateRequest, UserResponse,
    UsersListResponse, UserProfileResponse
)
from ...schemas.auth import ChangePasswordRequest, StandardResponse, UserActivityResponse
from ...auth.dependencies import get_current_user, get_current_admin_user, get_tenant_filter, CurrentUser, TenantFilter
from ...auth.jwt_handler import PasswordHandler

router = APIRouter(prefix="/users", tags=["Users"])


# PUBLIC_INTERFACE
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
            summary="Create new user",
            description="Create a new user within the current tenant (admin only).")
async def create_user(
    request: UserCreateRequest,
    current_user: CurrentUser = Depends(get_current_admin_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Create a new user within the tenant.
    
    Only administrators can create new users. If send_invitation is True,
    an invitation email will be sent to the user.
    """
    # Check for duplicate email within tenant
    existing_user = db.query(User).filter(
        User.tenant_id == tenant_filter.tenant_id,
        User.email == request.email
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists in this tenant"
        )
    
    # Create user with temporary password if invitation will be sent
    if request.send_invitation:
        # Generate temporary password
        import secrets
        temp_password = secrets.token_urlsafe(16)
        password_hash = PasswordHandler.hash_password(temp_password)
        # In real implementation, send invitation email
    else:
        # Generate random password - user will need to reset
        import secrets
        temp_password = secrets.token_urlsafe(16)
        password_hash = PasswordHandler.hash_password(temp_password)
    
    user = User(
        id=uuid4(),
        tenant_id=tenant_filter.tenant_id,
        email=request.email,
        password_hash=password_hash,
        first_name=request.first_name,
        last_name=request.last_name,
        role=UserRole(request.role)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        deactivated_at=user.deactivated_at,
        tenant_id=user.tenant_id,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.get("/", response_model=UsersListResponse,
           summary="List users",
           description="Get a paginated list of users in the current tenant (admin only).")
async def list_users(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    role: Optional[str] = Query(None, description="Filter by role"),
    q: Optional[str] = Query(None, description="Search query for name or email"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_admin_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    List users in the current tenant.
    
    Returns a paginated list of users with optional filtering.
    Only administrators can access this endpoint.
    """
    query = db.query(User).filter(User.tenant_id == tenant_filter.tenant_id)
    
    # Apply filters
    if active is not None:
        query = query.filter(User.active == active)
    
    if role:
        query = query.filter(User.role == UserRole(role))
    
    if q:
        query = query.filter(
            (User.first_name.ilike(f"%{q}%")) |
            (User.last_name.ilike(f"%{q}%")) |
            (User.email.ilike(f"%{q}%"))
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    user_responses = [
        UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            active=user.active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login=user.last_login,
            deactivated_at=user.deactivated_at,
            tenant_id=user.tenant_id,
            preferences=user.preferences
        )
        for user in users
    ]
    
    # Count statistics
    active_count = db.query(func.count(User.id)).filter(
        User.tenant_id == tenant_filter.tenant_id,
        User.active == True
    ).scalar() or 0
    
    admin_count = db.query(func.count(User.id)).filter(
        User.tenant_id == tenant_filter.tenant_id,
        User.role == UserRole.ADMIN
    ).scalar() or 0
    
    return UsersListResponse(
        users=user_responses,
        total=total,
        active_count=active_count,
        admin_count=admin_count
    )


# PUBLIC_INTERFACE
@router.get("/me", response_model=UserProfileResponse,
           summary="Get own profile",
           description="Get the current user's profile information.")
async def get_own_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile information.
    
    Returns the authenticated user's profile data.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.put("/me", response_model=UserProfileResponse,
           summary="Update own profile",
           description="Update the current user's profile information.")
async def update_own_profile(
    request: UserUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile.
    
    Allows users to update their own profile information.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.get("/{user_id}", response_model=UserResponse,
           summary="Get user details",
           description="Get detailed information about a specific user.")
async def get_user(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Get user details.
    
    Users can view their own profile, admins can view any user in the tenant.
    """
    # Check if user is viewing their own profile or is an admin
    if user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view other user's profile"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        deactivated_at=user.deactivated_at,
        tenant_id=user.tenant_id,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.put("/{user_id}", response_model=UserResponse,
           summary="Update user",
           description="Update user information (admin only or own profile).")
async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Update user information.
    
    Users can update their own profile, admins can update any user in the tenant.
    """
    # Check permissions
    if user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify other user's profile"
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        deactivated_at=user.deactivated_at,
        tenant_id=user.tenant_id,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.put("/{user_id}/role", response_model=UserResponse,
           summary="Update user role",
           description="Update a user's role within the tenant (admin only).")
async def update_user_role(
    user_id: UUID,
    role_data: dict,
    current_user: CurrentUser = Depends(get_current_admin_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Update user role.
    
    Only administrators can change user roles.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    new_role = role_data.get("role")
    if not new_role:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role is required"
        )
    
    try:
        user.role = UserRole(new_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid role"
        )
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        deactivated_at=user.deactivated_at,
        tenant_id=user.tenant_id,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.post("/{user_id}/deactivate", response_model=UserResponse,
            summary="Deactivate user",
            description="Deactivate a user account (admin only).")
async def deactivate_user(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_admin_user),
    tenant_filter: TenantFilter = Depends(get_tenant_filter),
    db: Session = Depends(get_db)
):
    """
    Deactivate a user account.
    
    Only administrators can deactivate users.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_filter.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.active = False
    from datetime import datetime, timezone
    user.deactivated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        deactivated_at=user.deactivated_at,
        tenant_id=user.tenant_id,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.post("/me/change-password", response_model=StandardResponse,
            summary="Change password",
            description="Change the current user's password.")
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change current user's password.
    
    Requires the current password for verification.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not PasswordHandler.verify_password(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if not PasswordHandler.validate_password_strength(request.new_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password does not meet requirements"
        )
    
    # Update password
    user.password_hash = PasswordHandler.hash_password(request.new_password)
    db.commit()
    
    return StandardResponse(message="Password changed successfully")


# PUBLIC_INTERFACE
@router.get("/me/activity", response_model=UserActivityResponse,
           summary="Get user activity log",
           description="Get the current user's activity log.")
async def get_user_activity(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's activity log.
    
    Returns a paginated list of user activities for security and audit purposes.
    """
    query = db.query(UserActivityLog).filter(
        UserActivityLog.user_id == current_user.user_id
    ).order_by(UserActivityLog.timestamp.desc())
    
    total = query.count()
    offset = (page - 1) * per_page
    activities = query.offset(offset).limit(per_page).all()
    
    from ...schemas.auth import UserActivityLog as ActivitySchema
    activity_responses = [
        ActivitySchema(
            id=activity.id,
            action=activity.action,
            timestamp=activity.timestamp,
            ip_address=activity.ip_address,
            user_agent=activity.user_agent,
            details=str(activity.details) if activity.details else None
        )
        for activity in activities
    ]
    
    return UserActivityResponse(
        activities=activity_responses,
        total=total
    )
