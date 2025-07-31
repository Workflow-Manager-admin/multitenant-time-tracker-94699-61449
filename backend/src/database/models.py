"""
SQLAlchemy database models for the multitenant time tracker.

Defines all database tables and relationships for tenants, users, clients,
projects, technologies, time entries, and related entities.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, Numeric, 
    ForeignKey, JSON, UniqueConstraint, Index, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    """User roles within a tenant."""
    ADMIN = "admin"
    USER = "user"


class ProjectStatus(str, enum.Enum):
    """Project status values."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class InvitationStatus(str, enum.Enum):
    """Invitation status values."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Tenant(Base):
    """Tenant model for multi-tenancy support."""
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    domain = Column(String(255), nullable=True)
    settings = Column(JSON, nullable=False, default=dict)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="tenant", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="tenant", cascade="all, delete-orphan")
    technologies = relationship("Technology", back_populates="tenant", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="tenant", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}')>"


class User(Base):
    """User model with tenant association."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    active = Column(Boolean, nullable=False, default=True)
    preferences = Column(JSON, nullable=False, default=dict)
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    time_entries = relationship("TimeEntry", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_user_email_per_tenant'),
        Index('idx_user_tenant_email', 'tenant_id', 'email'),
        Index('idx_user_active', 'active'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', tenant_id={self.tenant_id})>"


class PasswordResetToken(Base):
    """Password reset tokens for user authentication."""
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id})>"


class Invitation(Base):
    """Tenant invitations for user onboarding."""
    __tablename__ = "invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    token = Column(String(255), nullable=False, unique=True)
    status = Column(Enum(InvitationStatus), nullable=False, default=InvitationStatus.PENDING)
    message = Column(Text, nullable=True)
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="invitations")
    invited_by = relationship("User", foreign_keys=[invited_by_id])

    def __repr__(self):
        return f"<Invitation(id={self.id}, email='{self.email}', tenant_id={self.tenant_id})>"


class Client(Base):
    """Client model for project management."""
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="clients")
    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_client_name_per_tenant'),
        Index('idx_client_tenant_active', 'tenant_id', 'active'),
    )

    def __repr__(self):
        return f"<Client(id={self.id}, name='{self.name}', tenant_id={self.tenant_id})>"


class Project(Base):
    """Project model for time tracking."""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(ProjectStatus), nullable=False, default=ProjectStatus.ACTIVE)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    budget = Column(Numeric(12, 2), nullable=True)
    hourly_rate = Column(Numeric(8, 2), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="projects")
    client = relationship("Client", back_populates="projects")
    time_entries = relationship("TimeEntry", back_populates="project", cascade="all, delete-orphan")
    project_technologies = relationship("ProjectTechnology", back_populates="project", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'client_id', 'name', name='uq_project_name_per_tenant_client'),
        Index('idx_project_tenant_client', 'tenant_id', 'client_id'),
        Index('idx_project_status', 'status'),
    )

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', client_id={self.client_id})>"


class Technology(Base):
    """Technology model for categorizing work."""
    __tablename__ = "technologies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(100), nullable=True)
    version = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="technologies")
    project_technologies = relationship("ProjectTechnology", back_populates="technology", cascade="all, delete-orphan")
    time_entry_technologies = relationship("TimeEntryTechnology", back_populates="technology", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_technology_name_per_tenant'),
        Index('idx_technology_tenant_active', 'tenant_id', 'active'),
    )

    def __repr__(self):
        return f"<Technology(id={self.id}, name='{self.name}', tenant_id={self.tenant_id})>"


class ProjectTechnology(Base):
    """Association table for projects and technologies."""
    __tablename__ = "project_technologies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    technology_id = Column(UUID(as_uuid=True), ForeignKey("technologies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", back_populates="project_technologies")
    technology = relationship("Technology", back_populates="project_technologies")

    # Constraints
    __table_args__ = (
        UniqueConstraint('project_id', 'technology_id', name='uq_project_technology'),
    )

    def __repr__(self):
        return f"<ProjectTechnology(project_id={self.project_id}, technology_id={self.technology_id})>"


class TimeEntry(Base):
    """Time entry model for tracking work sessions."""
    __tablename__ = "time_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)  # Calculated field
    billable = Column(Boolean, nullable=False, default=True)
    hourly_rate = Column(Numeric(8, 2), nullable=True)
    amount = Column(Numeric(10, 2), nullable=True)  # Calculated field
    is_running = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant", back_populates="time_entries")
    user = relationship("User", back_populates="time_entries")
    project = relationship("Project", back_populates="time_entries")
    time_entry_technologies = relationship("TimeEntryTechnology", back_populates="time_entry", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        Index('idx_time_entry_tenant_user', 'tenant_id', 'user_id'),
        Index('idx_time_entry_project', 'project_id'),
        Index('idx_time_entry_start_time', 'start_time'),
        Index('idx_time_entry_running', 'is_running'),
    )

    def __repr__(self):
        return f"<TimeEntry(id={self.id}, user_id={self.user_id}, project_id={self.project_id})>"


class TimeEntryTechnology(Base):
    """Association table for time entries and technologies."""
    __tablename__ = "time_entry_technologies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    time_entry_id = Column(UUID(as_uuid=True), ForeignKey("time_entries.id"), nullable=False)
    technology_id = Column(UUID(as_uuid=True), ForeignKey("technologies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    time_entry = relationship("TimeEntry", back_populates="time_entry_technologies")
    technology = relationship("Technology", back_populates="time_entry_technologies")

    # Constraints
    __table_args__ = (
        UniqueConstraint('time_entry_id', 'technology_id', name='uq_time_entry_technology'),
    )

    def __repr__(self):
        return f"<TimeEntryTechnology(time_entry_id={self.time_entry_id}, technology_id={self.technology_id})>"


class UserActivityLog(Base):
    """User activity log for security and audit purposes."""
    __tablename__ = "user_activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)  # Support IPv6
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")

    # Constraints
    __table_args__ = (
        Index('idx_activity_log_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_activity_log_action', 'action'),
    )

    def __repr__(self):
        return f"<UserActivityLog(id={self.id}, user_id={self.user_id}, action='{self.action}')>"
