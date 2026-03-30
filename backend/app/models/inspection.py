"""
Inspection database model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base


class Inspection(Base):
    """Inspection session entity"""
    __tablename__ = "inspections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    container_id = Column(String, ForeignKey("containers.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    stage = Column(String, nullable=True)  # "pre", "post", or None
    status = Column(String, nullable=False)  # "ok", "alert"
    risk_score = Column(Integer, default=0)
    contamination_index = Column(Integer, default=1)
    contamination_label = Column(String, default="Low")
    
    # GPT summaries
    scene_caption = Column(Text, nullable=True)
    anomaly_summary = Column(Text, nullable=True)
    
    # Metadata
    people_nearby = Column(Boolean, default=False)
    door_status = Column(String, nullable=True)
    anomalies_present = Column(Boolean, default=False)
    
    # Relationships
    container = relationship("Container", back_populates="inspections")
    frames = relationship("Frame", back_populates="inspection", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Inspection(id={self.id}, container_id='{self.container_id}', status='{self.status}')>"
