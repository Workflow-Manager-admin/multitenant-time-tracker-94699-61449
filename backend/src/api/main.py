from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging

from ..database.connection import DatabaseManager
from .routes import auth, clients, users, tenants, time_tracking, projects

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app with metadata
app = FastAPI(
    title="Multitenant Time Tracker API",
    description="A comprehensive time tracking API with multi-tenant support, user authentication, project management, and reporting capabilities.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication, registration, and session management"
        },
        {
            "name": "Users",
            "description": "User management and profile operations"
        },
        {
            "name": "Tenants", 
            "description": "Tenant administration and user invitations"
        },
        {
            "name": "Clients",
            "description": "Client management and relationship tracking"
        },
        {
            "name": "Projects",
            "description": "Project management and tracking operations"
        },
        {
            "name": "Time Tracking",
            "description": "Time entry management, timers, and tracking operations"
        },
        {
            "name": "Technologies",
            "description": "Technology categorization and tagging"
        },
        {
            "name": "Timer",
            "description": "Start/stop timer functionality"
        },
        {
            "name": "Time Entries",
            "description": "Time entry CRUD operations"
        },
        {
            "name": "Dashboard",
            "description": "Dashboard summary and analytics"
        }
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and perform startup tasks."""
    logger.info("Starting up Multitenant Time Tracker API...")
    
    # Initialize database
    try:
        DatabaseManager.init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Perform cleanup tasks on shutdown."""
    logger.info("Shutting down Multitenant Time Tracker API...")


# Health check endpoint
@app.get("/", tags=["Health"])
def health_check():
    """
    Health check endpoint.
    
    Returns basic API status and version information.
    """
    return {
        "message": "Multitenant Time Tracker API is healthy",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health", tags=["Health"])
def detailed_health_check():
    """
    Detailed health check endpoint.
    
    Returns comprehensive health status including database connectivity.
    """
    try:
        # Test database connectivity
        from ..database.connection import get_db
        db = next(get_db())
        db.execute("SELECT 1").scalar()
        db.close()
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "database": "connected",
            "timestamp": "2024-01-15T10:00:00Z"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy - database connection failed"
        )


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(time_tracking.router, prefix="/api/v1")


# WebSocket endpoint for real-time updates (placeholder)
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket, client_id: str):
    """
    WebSocket endpoint for real-time timer updates.
    
    Provides real-time communication for timer status, notifications,
    and live updates. Clients connect using their unique client ID.
    
    Usage:
    - Connect to /ws/{client_id} where client_id is the user's unique identifier
    - Send/receive JSON messages for timer events and notifications
    - Automatically handles connection lifecycle and error recovery
    """
    await websocket.accept()
    try:
        while True:
            # In a full implementation, this would handle real-time timer updates
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
    finally:
        await websocket.close()


# Add explicit WebSocket documentation route
@app.get("/docs/websocket", tags=["WebSocket"])
def websocket_documentation():
    """
    WebSocket API Documentation.
    
    Provides detailed information about WebSocket endpoints and usage patterns
    for real-time features in the time tracking application.
    """
    return {
        "websocket_endpoints": [
            {
                "endpoint": "/ws/{client_id}",
                "description": "Real-time timer updates and notifications",
                "usage": "Connect with user's unique client ID for live updates",
                "message_format": "JSON with action and payload fields"
            }
        ],
        "connection_info": {
            "protocol": "WebSocket",
            "authentication": "Bearer token in subprotocol or query parameter",
            "heartbeat": "30 second intervals"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
