"""
API routes entry point
"""
from fastapi import APIRouter

# Import the routers from your sub-modules
from .analysis import router as analysis_router
from .history import router as history_router
from .training import router as training_router
from .metrics import router as metrics_router
from .video_session import router as video_router 

api_router = APIRouter()

# Registering the routes with their respective prefixes and tags
api_router.include_router(video_router) # Prefix "/video-session" is already in the file
api_router.include_router(analysis_router, prefix="/analyze", tags=["Analysis"])
api_router.include_router(history_router, prefix="/history", tags=["History"])
api_router.include_router(training_router, prefix="/training", tags=["Training"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])

__all__ = ["api_router"]