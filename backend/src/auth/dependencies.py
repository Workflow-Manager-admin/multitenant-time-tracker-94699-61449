"""
Authentication dependencies for FastAPI endpoints.

Provides dependency functions for extracting user information, tenant context,
and enforcing authentication/authorization requirements.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from uuid import UUID

from ..database.connection import get_db
from ..database.models import Tenant
from .jwt_handler import JWTHandler

security = HTTPBearer()


class CurrentUser:
    """Current user information from JWT token."""
    
    def __init__(self, user_id: UUID, tenant_id: UUID, email: str, role: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.email = email
        self.role = role
        self.is_admin = role == "admin"


# PUBLIC_INTERFACE
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> CurrentUser:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        db: Database session
        
    Returns:
        CurrentUser: Current user information
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = JWTHandler.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        email: str = payload.get("email")
        role: str = payload.get("role")
        
        if user_id is None or tenant_id is None:
            raise credentials_exception
            
        return CurrentUser(
            user_id=UUID(user_id),
            tenant_id=UUID(tenant_id),
            email=email,
            role=role
        )
    except Exception:
        raise credentials_exception


# PUBLIC_INTERFACE
async def get_current_admin_user(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Get current user and ensure they have admin role.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        CurrentUser: Current admin user
        
    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user


# PUBLIC_INTERFACE
async def get_tenant_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Get tenant context from header or current user.
    
    Args:
        x_tenant_id: Tenant ID from header
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Tenant: Tenant object
        
    Raises:
        HTTPException: If tenant not found or access denied
    """
    # Use tenant from header if provided, otherwise use user's tenant
    tenant_id = UUID(x_tenant_id) if x_tenant_id else current_user.tenant_id
    
    # Verify user has access to this tenant
    if tenant_id != current_user.tenant_id:
        # In a full implementation, you'd check if user has access to multiple tenants
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this tenant is not allowed"
        )
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.active == True).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    return tenant


# PUBLIC_INTERFACE
async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[CurrentUser]:
    """
    Get current user if authenticated, None otherwise.
    
    Args:
        credentials: Optional HTTP authorization credentials
        db: Database session
        
    Returns:
        Optional[CurrentUser]: Current user if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


class TenantFilter:
    """Helper class for applying tenant-based filtering to database queries."""
    
    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
    
    def filter_query(self, query, model_class):
        """Apply tenant filter to a SQLAlchemy query."""
        return query.filter(model_class.tenant_id == self.tenant_id)


# PUBLIC_INTERFACE
async def get_tenant_filter(
    tenant: Tenant = Depends(get_tenant_context)
) -> TenantFilter:
    """
    Get tenant filter for database queries.
    
    Args:
        tenant: Current tenant context
        
    Returns:
        TenantFilter: Tenant filter utility
    """
    return TenantFilter(tenant.id)
