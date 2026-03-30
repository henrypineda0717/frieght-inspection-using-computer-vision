import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- APP INFO ---
    APP_NAME: str = "Container Inspection System"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # --- PATH RESOLUTION ---
    # backend/app/config.py -> backend/app -> backend -> Project Root
    ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # Storage Hierarchy
    STORAGE_ROOT: Path = ROOT_DIR / "storage"
    INSPECTION_STORAGE: Path = STORAGE_ROOT / "inspections"
    MODELS_DIR: Path = ROOT_DIR / "models"
    DATABASE_URL: str = f"sqlite:///{ROOT_DIR}/inspections.db"

    # --- MODEL SETTINGS ---
    GENERAL_MODEL_PATH: str = "yolo11n.pt"
    YOLOE_MODEL_PATH: str = "container_front.pt"
    RT_DETR_MODEL_PATH: str = "checkpoint_best_ema.pth"
    
    YOLOE_REAR_MODEL_PATH: Optional[str] = None 
    RT_DETR_DEFECT_MODEL_PATH: Optional[str] = None
    OCR_MODEL_TYPE: str = "paddle_v5"

    # --- AI THRESHOLDS ---
    GENERAL_MODEL_CONFIDENCE: float = 0.5
    DAMAGE_MODEL_CONFIDENCE: float = 0.15
    ID_MODEL_CONFIDENCE: float = 0.5
    DEFECT_CONFIDENCE: float = 0.15
    
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    GEMINI_REVIEW_TEMPERATURE: float = 0.25

    USE_FP16: bool = True
    USE_GPU: bool = True
    
    # --- VIDEO & UPLOAD ---
    VIDEO_SAMPLE_INTERVAL: float = 2.0
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024 # 100MB
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

# Create directories on startup
settings.INSPECTION_STORAGE.mkdir(parents=True, exist_ok=True)
settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
(settings.ROOT_DIR / "logs").mkdir(parents=True, exist_ok=True)
