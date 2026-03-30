"""
Frame database model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base


class Frame(Base):
    """Analyzed frame entity"""
    __tablename__ = "frames"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id"), nullable=False)
    image_path = Column(String, nullable=False)  # Relative path to stored image
    overlay_path = Column(String, nullable=True)  # Path to image with overlays
    contamination_index = Column(Integer, default=1)
    status = Column(String, nullable=False)  # "ok", "alert"
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    inspection = relationship("Inspection", back_populates="frames")
    detections = relationship("Detection", back_populates="frame", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Frame(id={self.id}, inspection_id={self.inspection_id}, status='{self.status}')>"
