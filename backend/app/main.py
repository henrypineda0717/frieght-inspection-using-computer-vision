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
from app.api.camera_stream import router as camera_stream_router
from app.api.config import HLS_BASE_DIR

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description="AI-powered container inspection system with YOLO detection and GPT analysis"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    from datetime import datetime
    from app.utils.metrics import metrics_collector
    from app.services.model_manager import ModelManager
    from app.utils.logger import get_logger
    
    logger = get_logger(__name__)
    
    metrics_collector.set_startup_time(datetime.utcnow())
    
    log_level = "DEBUG" if settings.DEBUG else "INFO"
    log_file = settings.ROOT_DIR / "logs" / "app.log"
    setup_logging(level=log_level, log_file=log_file)
    
    init_db()
    
    logger.info("Loading YOLO models at startup...")
    model_manager = ModelManager()
    status = model_manager.load_models()
    loaded_count = sum(status.values())
    logger.info(f"Model loading complete: {loaded_count}/3 models loaded")
    print(f"✓ Models loaded: {loaded_count}/3")
    
    print(f"✓ {settings.APP_NAME} v{settings.APP_VERSION} started")
    print(f"✓ Database: {settings.DATABASE_URL}")
    print(f"✓ Storage: {settings.STORAGE_ROOT}")

app.include_router(api_router, prefix="/api")
app.include_router(video_session_router)
app.include_router(camera_stream_router)

# ---------- MOVED THESE FOUR ENDPOINTS BEFORE STATIC MOUNTS ----------
@app.get("/")
async def index():
    index_path = settings.ROOT_DIR / "frontend" / "pages" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not found. Please ensure frontend files are in the correct location."}

@app.get("/history.html")
async def history():
    history_path = settings.ROOT_DIR / "frontend" / "pages" / "history.html"
    if history_path.exists():
        return FileResponse(history_path)
    return {"message": "History page not found"}

@app.get("/api/images/{path:path}")
async def serve_image(path: str):
    from app.services.storage_service import StorageService
    
    storage_service = StorageService()
    full_path = storage_service.get_absolute_path(path)
    
    if not full_path.exists():
        return {"error": "Image not found"}, 404
    
    return FileResponse(full_path)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME
    }
# ---------------------------------------------------------------------

# Static mounts (exactly as in your original)
frontend_dir = settings.ROOT_DIR / "frontend"

if frontend_dir.exists():
    assets_dir = frontend_dir / "assets"
    pages_dir = frontend_dir / "pages"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

if pages_dir.exists():
    app.mount("/", StaticFiles(directory=str(pages_dir), html=True), name="pages")

# Serve HLS output directory
app.mount("/hls", StaticFiles(directory=str(HLS_BASE_DIR)), name="hls")

# Optional storage mount
if settings.STORAGE_ROOT.exists():
    app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_ROOT)), name="storage")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
