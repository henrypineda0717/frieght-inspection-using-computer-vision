"""
Detection schemas
"""
from typing import List, Optional
from pydantic import BaseModel


class BBox(BaseModel):
    """Bounding box"""
    x: int
    y: int
    w: int
    h: int


class DetectionCreate(BaseModel):
    """Schema for creating a detection"""
    label: str
    category: Optional[str] = None
    confidence: Optional[float] = None
    bbox: Optional[BBox] = None
    severity: Optional[str] = None
    defect_type: Optional[str] = None
    model_source: Optional[str] = "general"  # NEW: Model source (general/damage/id)
    container_id: Optional[str] = None  # NEW: Container ID from OCR (for ID detections)
    iso_type: Optional[str] = None                     # <-- NEW
    corners: Optional[List[List[float]]] = None        # <-- NEW


class DetectionResponse(BaseModel):
    """Schema for detection response"""
    id: int
    label: str
    category: Optional[str]
    confidence: Optional[float]
    bbox_x: Optional[int]
    bbox_y: Optional[int]
    bbox_w: Optional[int]
    bbox_h: Optional[int]
    severity: Optional[str]
    defect_type: Optional[str]
    legend: Optional[str] = None
    model_source: Optional[str] = "general"  # NEW: Model source
    container_id: Optional[str] = None  # NEW: Container ID from OCR
    
    class Config:
        from_attributes = True
