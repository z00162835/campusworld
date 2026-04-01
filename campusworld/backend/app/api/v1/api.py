"""
Main API router for CampusWorld
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, command

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(command.router, prefix="/command", tags=["commands"])
