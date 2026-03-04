"""
Analysis request/response schemas
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from .detection import DetectionCreate, BBox


class AnalyzeRequest(BaseModel):
    """Schema for analysis request"""
    damage_sensitivity: str = "medium"
    inspection_stage: Optional[str] = None
    spot_mode: str = "auto"
    vision_backend: str = "auto"
    use_vision_gpt: bool = True
    use_text_gpt: bool = True


class DiffEntry(BaseModel):
    """Difference entry for pre/post comparison"""
    label: str
    category: Optional[str] = None
    bbox: Optional[BBox] = None


class StageDiff(BaseModel):
    """Stage difference"""
    reference_stage: str
    new_findings: List[DiffEntry] = Field(default_factory=list)
    resolved_findings: List[DiffEntry] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """Schema for analysis response"""
    container_id: str
    container_type: Optional[str] = None
    status: str
    detections: List[DetectionCreate]
    timestamp: str
    
    people_nearby: bool = False
    door_status: Optional[str] = None
    lock_boxes: List[BBox] = Field(default_factory=list)
    anomalies_present: bool = False
    
    inspection_stage: Optional[str] = None
    diff: Optional[StageDiff] = None
    
    scene_tags: List[str] = Field(default_factory=list)
    risk_score: int = 0
    risk_explanations: List[str] = Field(default_factory=list)
    
    prewash_remarks: List[DiffEntry] = Field(default_factory=list)
    resolved_remarks: List[DiffEntry] = Field(default_factory=list)
    
    contamination_index: int = 1
    contamination_label: str = "Low"
    contamination_scale: List[bool] = Field(default_factory=list)
    
    scene_caption: Optional[str] = None
    semantic_people_count: Optional[int] = None
    anomaly_summary: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    
    inspection_id: Optional[int] = None  # Added after persistence
