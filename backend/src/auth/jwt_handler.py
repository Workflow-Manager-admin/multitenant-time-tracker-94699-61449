"""
JWT token handling for authentication and authorization.

Provides utilities for creating, validating, and decoding JWT tokens
with tenant and user information.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from uuid import UUID

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class JWTHandler:
    """JWT token handler for authentication."""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Token payload data
            expires_delta: Token expiration delta
            
        Returns:
            str: Encoded JWT token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Optional[Dict[str, Any]]: Token payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def create_user_token(user_id: UUID, tenant_id: UUID, email: str, role: str) -> str:
        """
        Create a JWT token for a user.
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            email: User email
            role: User role
            
        Returns:
            str: JWT token
        """
        data = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "email": email,
            "role": role,
            "type": "access"
        }
        return JWTHandler.create_access_token(data)
    
    @staticmethod
    def create_reset_token(user_id: UUID) -> str:
        """
        Create a password reset token.
        
        Args:
            user_id: User ID
            
        Returns:
            str: Reset token
        """
        data = {
            "sub": str(user_id),
            "type": "reset",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)  # 1 hour expiry
        }
        return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def verify_reset_token(token: str) -> Optional[UUID]:
        """
        Verify a password reset token.
        
        Args:
            token: Reset token to verify
            
        Returns:
            Optional[UUID]: User ID if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "reset":
                return None
            return UUID(payload.get("sub"))
        except (JWTError, ValueError):
            return None
    
    @staticmethod
    def create_invitation_token(email: str, tenant_id: UUID, role: str) -> str:
        """
        Create an invitation token.
        
        Args:
            email: Invitee email
            tenant_id: Tenant ID
            role: Assigned role
            
        Returns:
            str: Invitation token
        """
        data = {
            "email": email,
            "tenant_id": str(tenant_id),
            "role": role,
            "type": "invitation",
            "exp": datetime.now(timezone.utc) + timedelta(days=7)  # 7 days expiry
        }
        return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    def verify_invitation_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify an invitation token.
        
        Args:
            token: Invitation token to verify
            
        Returns:
            Optional[Dict[str, Any]]: Token data if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "invitation":
                return None
            return payload
        except JWTError:
            return None


class PasswordHandler:
    """Password handling utilities."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password.
        
        Args:
            password: Plain text password
            
        Returns:
            str: Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """
        Validate password strength.
        
        Args:
            password: Password to validate
            
        Returns:
            bool: True if password meets requirements
        """
        if len(password) < 8:
            return False
        # Add more validation rules as needed
        return True


# PUBLIC_INTERFACE
def get_password_hash(password: str) -> str:
    """
    Get password hash.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    return PasswordHandler.hash_password(password)


# PUBLIC_INTERFACE
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        bool: True if password matches
    """
    return PasswordHandler.verify_password(plain_password, hashed_password)


# PUBLIC_INTERFACE
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Token payload
        expires_delta: Optional expiration delta
        
    Returns:
        str: JWT token
    """
    return JWTHandler.create_access_token(data, expires_delta)
