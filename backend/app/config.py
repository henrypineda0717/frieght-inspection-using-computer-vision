import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Container Inspection System"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    DATABASE_URL: str = "sqlite:///./inspections.db"
    
    ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_ROOT: Path = ROOT_DIR / "storage" / "inspections"
    MODELS_DIR: Path = ROOT_DIR / "models"
    
    # Model Paths
    GENERAL_MODEL_PATH: str = "yolo11n.pt"
    YOLOE_MODEL_PATH: str = "container_front.pt"
    RT_DETR_MODEL_PATH: str = "checkpoint_best_ema.pth"
    
    # These were missing and causing the "Extra inputs" error
    YOLOE_REAR_MODEL_PATH: Optional[str] = None 
    RT_DETR_DEFECT_MODEL_PATH: Optional[str] = None
    OCR_MODEL_TYPE: str = "paddle_v5"
    
    # Confidence & Settings
    GENERAL_MODEL_CONFIDENCE: float = 0.5
    DAMAGE_MODEL_CONFIDENCE: float = 0.15
    ID_MODEL_CONFIDENCE: float = 0.5
    REAR_CONFIDENCE: float = 0.65
    DEFECT_CONFIDENCE: float = 0.15
    
    # Performance & Display
    USE_FP16: bool = True
    USE_GPU: bool = True
    QUICK_MODE: bool = False
    MODEL_WARMUP: bool = True
    Y_IMGSZ: int = 640 # placeholder for varying sizes
    REAR_IMGSZ: int = 640
    INTERIOR_IMGSZ: int = 640
    DEFAULT_IMGSZ: int = 640
    
    FRAME_SAMPLE_RATE: int = 1
    OCR_GPU: bool = False
    
    MIN_CONFIDENCE: float = 0.5
    MIN_BOX_AREA_RATIO: float = 0.0002
    
    RETENTION_DAYS: int = 90
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    
    VIDEO_SAMPLE_INTERVAL: float = 2.0
    MAX_ANALYZED_FRAMES: int = 40
    VIDEO_BATCH_SIZE: int = 50
    
    CORS_ORIGINS: list[str] = ["*"]
    
    # Change 'forbid' to 'ignore' to prevent crashing on extra .env variables
    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=True, 
        extra="ignore" 
    )


settings = Settings()

settings.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)