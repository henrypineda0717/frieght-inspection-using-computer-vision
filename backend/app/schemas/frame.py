"""
Frame schemas
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from .detection import DetectionResponse


class FrameCreate(BaseModel):
    """Schema for creating a frame"""
    image_path: str
    overlay_path: Optional[str] = None
    contamination_index: int = 1
    status: str = "ok"


class FrameResponse(BaseModel):
    """Schema for frame response"""
    id: int
    image_path: str
    overlay_path: Optional[str]
    contamination_index: int
    status: str
    timestamp: datetime
    detections: List[DetectionResponse] = []
    
    class Config:
        from_attributes = True
