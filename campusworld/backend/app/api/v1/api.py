"""
Main API router for CampusWorld
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, command, ontology, graph, worlds
from app.api.v1 import accounts

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(command.router, prefix="/command", tags=["commands"])
api_router.include_router(accounts.router, tags=["账号管理"])
api_router.include_router(ontology.router, tags=["ontology"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(worlds.router, tags=["graph-world-scope"])
