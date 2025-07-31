"""
Authentication API routes.

Provides endpoints for user registration, login, password reset,
tenant selection, and authentication management.
"""
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4, UUID

from ...database.connection import get_db
from ...database.models import User, Tenant, PasswordResetToken, UserRole
from ...schemas.auth import (
    UserRegistrationRequest, UserLoginRequest, PasswordResetRequest,
    PasswordResetConfirm, TenantSelectionRequest,
    AuthResponse, RegistrationResponse, TokenRefreshResponse,
    TenantSelectionResponse, TenantsListResponse,
    StandardResponse, UserInfo, TenantInfo
)
from ...auth.dependencies import get_current_user, CurrentUser
from ...auth.jwt_handler import JWTHandler, PasswordHandler

router = APIRouter(prefix="/auth", tags=["Authentication"])


# PUBLIC_INTERFACE
@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED,
            summary="Register new user and tenant",
            description="Register a new user and create a new tenant. This endpoint creates both the user and tenant in a single operation.")
async def register_user(
    request: UserRegistrationRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user and create a new tenant.
    
    Creates a new tenant and user account, returning authentication tokens.
    The user becomes the admin of the newly created tenant.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Check if tenant name already exists
    existing_tenant = db.query(Tenant).filter(Tenant.name == request.tenant_name).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant with this name already exists"
        )
    
    # Validate password strength
    if not PasswordHandler.validate_password_strength(request.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password does not meet requirements"
        )
    
    # Create tenant
    tenant = Tenant(
        id=uuid4(),
        name=request.tenant_name,
        settings={"timezone": "UTC", "currency": "USD"}
    )
    db.add(tenant)
    db.flush()
    
    # Create user
    user = User(
        id=uuid4(),
        tenant_id=tenant.id,
        email=request.email,
        password_hash=PasswordHandler.hash_password(request.password),
        first_name=request.first_name,
        last_name=request.last_name,
        role=UserRole.ADMIN  # First user is admin
    )
    db.add(user)
    db.commit()
    
    # Create access token
    access_token = JWTHandler.create_user_token(
        user.id, tenant.id, user.email, user.role.value
    )
    
    return RegistrationResponse(
        user=UserInfo(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            active=user.active,
            current_tenant_id=tenant.id,
            preferences=user.preferences
        ),
        tenant=TenantInfo(
            id=tenant.id,
            name=tenant.name,
            role=user.role.value
        ),
        access_token=access_token
    )


# PUBLIC_INTERFACE
@router.post("/login", response_model=AuthResponse,
            summary="User login",
            description="Authenticate user with email and password, returning access token and available tenants.")
async def login_user(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access tokens.
    
    Validates user credentials and returns JWT token along with
    user information and available tenants.
    """
    # Find user by email
    user = db.query(User).filter(User.email == request.email, User.active == True).first()
    if not user or not PasswordHandler.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    
    # Get user's tenants (for now, just their primary tenant)
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id, Tenant.active == True).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User's tenant is not active"
        )
    
    # Create access token
    access_token = JWTHandler.create_user_token(
        user.id, tenant.id, user.email, user.role.value
    )
    
    return AuthResponse(
        access_token=access_token,
        user=UserInfo(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            active=user.active,
            current_tenant_id=tenant.id,
            preferences=user.preferences
        ),
        tenants=[TenantInfo(
            id=tenant.id,
            name=tenant.name,
            role=user.role.value
        )]
    )


# PUBLIC_INTERFACE
@router.post("/logout", response_model=StandardResponse,
            summary="User logout",
            description="Logout current user and invalidate tokens.")
async def logout_user(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Logout current user.
    
    In a full implementation, this would invalidate the token.
    For now, it just returns a success message.
    """
    return StandardResponse(message="Logged out successfully")


# PUBLIC_INTERFACE
@router.post("/refresh", response_model=TokenRefreshResponse,
            summary="Refresh access token",
            description="Refresh the current access token.")
async def refresh_token(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh the current access token.
    
    Creates a new access token for the authenticated user.
    """
    # Create new access token
    access_token = JWTHandler.create_user_token(
        current_user.user_id, current_user.tenant_id, 
        current_user.email, current_user.role
    )
    
    return TokenRefreshResponse(access_token=access_token)


# PUBLIC_INTERFACE
@router.get("/me", response_model=UserInfo,
           summary="Get current user",
           description="Get information about the currently authenticated user.")
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information.
    
    Returns detailed information about the currently authenticated user.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserInfo(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.value,
        active=user.active,
        current_tenant_id=current_user.tenant_id,
        preferences=user.preferences
    )


# PUBLIC_INTERFACE
@router.post("/password-reset-request", response_model=StandardResponse,
            summary="Request password reset",
            description="Request a password reset email to be sent.")
async def request_password_reset(
    request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset for user.
    
    Sends a password reset email to the user if the email exists.
    Always returns success to prevent email enumeration.
    """
    user = db.query(User).filter(User.email == request.email, User.active == True).first()
    if user:
        # Create password reset token
        reset_token = PasswordResetToken(
            id=uuid4(),
            user_id=user.id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        db.add(reset_token)
        db.commit()
        
        # In a real implementation, send email with reset link
        # send_password_reset_email(user.email, reset_token.token)
    
    return StandardResponse(message="Password reset email sent")


# PUBLIC_INTERFACE
@router.post("/password-reset-confirm", response_model=StandardResponse,
            summary="Confirm password reset",
            description="Confirm password reset with token and set new password.")
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm password reset and set new password.
    
    Uses the reset token to validate the request and updates the user's password.
    """
    # Find valid reset token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.token,
        PasswordResetToken.used == False,
        PasswordResetToken.expires_at > datetime.now(timezone.utc)
    ).first()
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Validate password strength
    if not PasswordHandler.validate_password_strength(request.new_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password does not meet requirements"
        )
    
    # Update user password
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    user.password_hash = PasswordHandler.hash_password(request.new_password)
    
    # Mark token as used
    reset_token.used = True
    
    db.commit()
    
    return StandardResponse(message="Password reset successful")


# PUBLIC_INTERFACE
@router.post("/select-tenant", response_model=TenantSelectionResponse,
            summary="Select active tenant",
            description="Select which tenant to work with for multi-tenant users.")
async def select_tenant(
    request: TenantSelectionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Select active tenant for user.
    
    For now, users can only access their primary tenant.
    This endpoint validates tenant access.
    """
    # In this implementation, users only have access to their primary tenant
    if request.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this tenant is not allowed"
        )
    
    tenant = db.query(Tenant).filter(
        Tenant.id == request.tenant_id,
        Tenant.active == True
    ).first()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return TenantSelectionResponse(
        message="Tenant selected successfully",
        current_tenant=TenantInfo(
            id=tenant.id,
            name=tenant.name,
            role=current_user.role
        )
    )


# PUBLIC_INTERFACE
@router.get("/tenants", response_model=TenantsListResponse,
           summary="Get user's tenants",
           description="Get list of tenants the user has access to.")
async def get_user_tenants(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get tenants available to current user.
    
    Returns list of tenants the user has access to.
    """
    tenant = db.query(Tenant).filter(
        Tenant.id == current_user.tenant_id,
        Tenant.active == True
    ).first()
    
    if not tenant:
        return TenantsListResponse(tenants=[])
    
    return TenantsListResponse(
        tenants=[TenantInfo(
            id=tenant.id,
            name=tenant.name,
            role=current_user.role
        )]
    )


# PUBLIC_INTERFACE
@router.post("/accept-invitation", response_model=RegistrationResponse,
            status_code=status.HTTP_201_CREATED,
            summary="Accept tenant invitation",
            description="Accept an invitation to join a tenant.")
async def accept_invitation(
    request_data: dict,  # Using dict to handle different request formats
    db: Session = Depends(get_db)
):
    """
    Accept tenant invitation and create user account.
    
    Validates the invitation token and creates a new user account
    associated with the inviting tenant.
    """
    token = request_data.get("token")
    password = request_data.get("password")
    first_name = request_data.get("first_name")
    last_name = request_data.get("last_name")
    
    if not all([token, password, first_name, last_name]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required fields"
        )
    
    # Verify invitation token
    token_data = JWTHandler.verify_invitation_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation token"
        )
    
    email = token_data["email"]
    tenant_id = UUID(token_data["tenant_id"])
    role = token_data["role"]
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Get tenant
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.active == True).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Create user
    user = User(
        id=uuid4(),
        tenant_id=tenant_id,
        email=email,
        password_hash=PasswordHandler.hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole(role)
    )
    db.add(user)
    db.commit()
    
    # Create access token
    access_token = JWTHandler.create_user_token(
        user.id, tenant.id, user.email, user.role.value
    )
    
    return RegistrationResponse(
        user=UserInfo(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.value,
            active=user.active,
            current_tenant_id=tenant.id,
            preferences=user.preferences
        ),
        tenant=TenantInfo(
            id=tenant.id,
            name=tenant.name,
            role=user.role.value
        ),
        access_token=access_token
    )
