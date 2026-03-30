"""
Detection database model
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Index
from sqlalchemy.orm import relationship

from .base import Base


class Detection(Base):
    """Object detection entity"""
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    frame_id = Column(Integer, ForeignKey("frames.id"), nullable=False)
    label = Column(String, nullable=False)
    category = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    
    # BBox coordinates
    bbox_x = Column(Integer, nullable=True)
    bbox_y = Column(Integer, nullable=True)
    bbox_w = Column(Integer, nullable=True)
    bbox_h = Column(Integer, nullable=True)
    
    # Additional metadata
    severity = Column(String, nullable=True)  # "high", "medium", "low"
    defect_type = Column(String, nullable=True)  # "dirt", "damage", "other"
    
    # Multi-model support
    model_source = Column(String(20), nullable=False, default='general')  # "general", "damage", "id"
    container_id = Column(String(11), ForeignKey("containers.id"), nullable=True)  # ISO 6346 format
    
    # NEW COLUMNS for video defect tracking
    track_id = Column(Integer, nullable=True)          # ByteTrack ID (for video)
    thumbnail_path = Column(String, nullable=True)     # relative path to saved thumbnail
    
    # Relationships
    frame = relationship("Frame", back_populates="detections")
    container = relationship("Container", back_populates="detections")

    # Index for efficient filtering by model_source
    __table_args__ = (
        Index('idx_model_source', 'model_source'),
    )
    
    def __repr__(self):
        return f"<Detection(id={self.id}, label='{self.label}', confidence={self.confidence}, model_source='{self.model_source}')>"
