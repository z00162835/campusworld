"""
Main API router for CampusWorld
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, campus, world

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(campus.router, prefix="/campus", tags=["campus"])
api_router.include_router(world.router, prefix="/world", tags=["world"])
