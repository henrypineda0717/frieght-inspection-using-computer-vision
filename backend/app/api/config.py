import os
from pathlib import Path

from app.config import settings

STORAGE_ROOT: Path = settings.STORAGE_ROOT

HLS_BASE_DIR: Path = STORAGE_ROOT / "hls"
HLS_BASE_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_SOURCE: Path = STORAGE_ROOT / "videos"
VIDEO_SOURCE.mkdir(parents=True, exist_ok=True)

BACKEND_URL: str = os.environ.get("BACKEND_URL") or f"http://localhost:{settings.PORT}"
DISPLAY_WIDTH: int = int(os.environ.get("DISPLAY_WIDTH", "1280"))
DISPLAY_HEIGHT: int = int(os.environ.get("DISPLAY_HEIGHT", "720"))
