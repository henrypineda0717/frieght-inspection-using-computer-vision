import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .stream_manager import SingleCameraManager
from .config import HLS_BASE_DIR

router = APIRouter(prefix="/camera-stream", tags=["Camera Stream"])

manager = SingleCameraManager()
manager_lock = asyncio.Lock()


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
    playlist_path = HLS_BASE_DIR / (status["cam_id"] or "") / "playlist.m3u8"
    for _ in range(6):
        if playlist_path.exists():
            status["ready"] = True
            break
        await asyncio.sleep(0.5)
    else:
        status["ready"] = False
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
