"""
Container database model
"""
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base


class Container(Base):
    """Container entity following ISO 6346 standard"""
    __tablename__ = "containers"
    
    id = Column(String(11), primary_key=True)  # Full Container ID (e.g., MSCU1234567) - ISO 6346 format
    owner_code = Column(String(3), nullable=True)  # First 3 letters (e.g., "MSK" for Maersk)
    category = Column(String(1), nullable=True)  # 4th letter: U=freight, J=detachable, Z=trailer
    serial_number = Column(String(6), nullable=True)  # 6-digit serial number
    check_digit = Column(Integer, nullable=True)  # ISO 6346 check digit (0-9)
    iso_type = Column(String, nullable=True)  # Container type code (e.g., "45R1", "42R1")
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    detection_count = Column(Integer, default=0, nullable=False)  # Number of times detected
    
    # Relationships
    inspections = relationship("Inspection", back_populates="container", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="container")
    
    def __repr__(self):
        return f"<Container(id='{self.id}', owner_code='{self.owner_code}', detection_count={self.detection_count})>"
