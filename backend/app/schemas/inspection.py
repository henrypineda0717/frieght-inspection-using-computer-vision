"""
Inspection schemas
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from .frame import FrameResponse


class InspectionCreate(BaseModel):
    """Schema for creating an inspection"""
    container_id: str
    stage: Optional[str] = None
    status: str = "ok"
    risk_score: int = 0
    contamination_index: int = 1


class InspectionSummary(BaseModel):
    """Schema for inspection list item"""
    id: int
    container_id: str
    iso_type: Optional[str]
    timestamp: datetime
    stage: Optional[str]
    status: str
    risk_score: int
    contamination_index: int
    contamination_label: str
    frame_count: int
    detection_count: int
    
    class Config:
        from_attributes = True


class InspectionDetail(BaseModel):
    """Schema for detailed inspection view"""
    id: int
    container_id: str
    iso_type: Optional[str]
    timestamp: datetime
    stage: Optional[str]
    status: str
    risk_score: int
    contamination_index: int
    contamination_label: str
    scene_caption: Optional[str]
    anomaly_summary: Optional[str]
    people_nearby: bool
    door_status: Optional[str]
    anomalies_present: bool
    frames: List[FrameResponse] = []
    
    class Config:
        from_attributes = True


class InspectionResponse(BaseModel):
    """Schema for inspection response"""
    id: int
    container_id: str
    timestamp: datetime
    status: str
    
    class Config:
        from_attributes = True


class UpdateMetadataRequest(BaseModel):
    """Schema for updating inspection metadata"""
    container_id: Optional[str] = None
    iso_type: Optional[str] = None
