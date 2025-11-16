"""
Main API router for CampusWorld
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
