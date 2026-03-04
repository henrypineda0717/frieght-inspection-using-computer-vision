"""
Container Inspection System - Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import settings
from app.database import init_db
from app.api import api_router
from app.utils import setup_logging
from app.api.video_session import router as video_session_router

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description="AI-powered container inspection system with YOLO detection and GPT analysis"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    from datetime import datetime
    from app.utils.metrics import metrics_collector
    from app.services.model_manager import ModelManager
    from app.utils.logger import get_logger
    
    logger = get_logger(__name__)
    
    # Record startup time
    metrics_collector.set_startup_time(datetime.utcnow())
    
    # Set up logging
    log_level = "DEBUG" if settings.DEBUG else "INFO"
    log_file = settings.ROOT_DIR / "logs" / "app.log"
    setup_logging(level=log_level, log_file=log_file)
    
    # Initialize database
    init_db()
    
    # Load YOLO models once at startup (singleton pattern ensures reuse)
    logger.info("Loading YOLO models at startup...")
    model_manager = ModelManager()
    status = model_manager.load_models()
    loaded_count = sum(status.values())
    logger.info(f"Model loading complete: {loaded_count}/3 models loaded")
    print(f"✓ Models loaded: {loaded_count}/3")
    
    print(f"✓ {settings.APP_NAME} v{settings.APP_VERSION} started")
    print(f"✓ Database: {settings.DATABASE_URL}")
    print(f"✓ Storage: {settings.STORAGE_ROOT}")

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(video_session_router)


# # Serve frontend static files
# frontend_dir = settings.ROOT_DIR / "frontend"
# if frontend_dir.exists():
#     # Mount assets directory for CSS, JS, and images
#     assets_dir = frontend_dir / "assets"
#     app.mount("/", StaticFiles(directory=str(frontend_dir / "pages"), html=True), name="pages")
#     if assets_dir.exists():
#         app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

from fastapi.staticfiles import StaticFiles

frontend_dir = settings.ROOT_DIR / "frontend"

if frontend_dir.exists():
    assets_dir = frontend_dir / "assets"
    pages_dir = frontend_dir / "pages"

    # 1. Mount specific sub-directories FIRST
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # 2. Mount the root last as a fallback
    if pages_dir.exists():
        app.mount("/", StaticFiles(directory=str(pages_dir), html=True), name="pages")

# Serve frontend pages
@app.get("/")
async def index():
    """Serve main analysis page"""
    index_path = frontend_dir / "pages" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not found. Please ensure frontend files are in the correct location."}

@app.get("/history.html")
async def history():
    """Serve history viewer page"""
    history_path = frontend_dir / "pages" / "history.html"
    if history_path.exists():
        return FileResponse(history_path)
    return {"message": "History page not found"}

# Serve stored images
@app.get("/api/images/{path:path}")
async def serve_image(path: str):
    """Serve stored inspection images"""
    from app.services.storage_service import StorageService
    
    storage_service = StorageService()
    full_path = storage_service.get_absolute_path(path)
    
    if not full_path.exists():
        return {"error": "Image not found"}, 404
    
    return FileResponse(full_path)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME
    }

# Run with uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
