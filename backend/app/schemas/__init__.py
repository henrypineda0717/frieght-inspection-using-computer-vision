"""
Pydantic schemas for request/response validation
"""
from .detection import DetectionCreate, DetectionResponse, BBox
from .frame import FrameCreate, FrameResponse
from .inspection import InspectionCreate, InspectionResponse, InspectionSummary, InspectionDetail
from .container import ContainerResponse
from .analysis import AnalyzeResponse, AnalyzeRequest

__all__ = [
    "DetectionCreate",
    "DetectionResponse",
    "BBox",
    "FrameCreate",
    "FrameResponse",
    "InspectionCreate",
    "InspectionResponse",
    "InspectionSummary",
    "InspectionDetail",
    "ContainerResponse",
    "AnalyzeResponse",
    "AnalyzeRequest",
]
