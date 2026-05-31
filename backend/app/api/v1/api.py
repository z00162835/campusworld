"""
Main API router for CampusWorld
"""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, command, ontology, graph, worlds, world_interaction
from app.api.v1 import accounts
api_router = APIRouter()
api_router.include_router(auth.router, prefix='/auth', tags=['authentication'])
api_router.include_router(command.router, prefix='/command', tags=['commands'])
api_router.include_router(accounts.router, tags=['账号管理'])
api_router.include_router(ontology.router, tags=['ontology'])
api_router.include_router(graph.router, tags=['graph'])
api_router.include_router(worlds.router, tags=['graph-world-scope'])
api_router.include_router(world_interaction.world_sessions_router)
api_router.include_router(world_interaction.worlds_router)
api_router.include_router(world_interaction.decision_center_router)
api_router.include_router(world_interaction.semantic_map_router)
api_router.include_router(world_interaction.world_search_router)
api_router.include_router(world_interaction.world_history_router)
