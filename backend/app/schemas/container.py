"""
Container schemas
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ContainerResponse(BaseModel):
    """Schema for container response with ISO 6346 fields"""
    id: str
    owner_code: Optional[str]
    category: Optional[str]
    serial_number: Optional[str]
    check_digit: Optional[int]
    iso_type: Optional[str]
    last_seen: datetime
    inspection_count: int
    
    class Config:
        from_attributes = True
