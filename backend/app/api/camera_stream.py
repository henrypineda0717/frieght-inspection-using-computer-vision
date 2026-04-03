import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from .stream_manager import SingleCameraManager
from .config import HLS_BASE_DIR

router = APIRouter(prefix="/camera-stream", tags=["Camera Stream"])

manager = SingleCameraManager()
manager_lock = asyncio.Lock()


@router.post("/upload")
async def upload_camera_video(video: UploadFile = File(...)):
    storage_dir = settings.STORAGE_ROOT / "videos"
    storage_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(video.filename).suffix or ".mp4"
    target_path = storage_dir / f"camera-{uuid4().hex}{suffix}"
    try:
        data = await video.read()
        target_path.write_bytes(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save video: {exc}")
    return {"source": str(target_path)}


class CameraStreamStartRequest(BaseModel):
    name: str = Field(..., description="Friendly camera name")
    source: str = Field(..., description="RTSP or file path for the camera stream")


@router.post("/start")
async def start_camera_stream(payload: CameraStreamStartRequest):
    async with manager_lock:
        success = await manager.start(payload.dict())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start camera stream")
    status = manager.get_status()
    cam_id = status["cam_id"] or ""
    playlist_path = HLS_BASE_DIR / cam_id / "playlist.m3u8"
    status["ready"] = playlist_path.exists()
    while not status["ready"] and status["running"]:
        await asyncio.sleep(0.5)
        status = manager.get_status()
        playlist_path = HLS_BASE_DIR / (status["cam_id"] or cam_id) / "playlist.m3u8"
        status["ready"] = playlist_path.exists()
    return {"status": "running", **status}


@router.post("/stop")
async def stop_camera_stream():
    async with manager_lock:
        await manager.stop()
    return {"status": "stopped"}


@router.get("/status")
async def camera_stream_status():
    status = manager.get_status()
    playlist_path = HLS_BASE_DIR / (status["cam_id"] or "") / "playlist.m3u8"
    status["ready"] = playlist_path.exists()
    return status
