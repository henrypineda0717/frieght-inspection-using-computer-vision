"""
Unit tests for PersistenceService
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import numpy as np
import cv2

from app.models.base import Base
from app.models import Container, Inspection, Frame, Detection
from app.services.persistence_service import PersistenceService


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def persistence_service(db_session):
    """Create a PersistenceService instance with test database"""
    return PersistenceService(db_session)


def test_detection_persistence_with_model_source(db_session, persistence_service):
    """Test that detections are persisted with model_source field"""
    # Create a simple test image
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)
    _, encoded = cv2.imencode('.jpg', test_image)
    image_data = encoded.tobytes()
    
    # Create analysis result with multi-model detections
    analysis_result = {
        "container_id": "TEST1234567",
        "status": "ok",
        "detections": [
            {
                "label": "container",
                "confidence": 0.95,
                "model_source": "general",
                "bbox": {"x": 10, "y": 10, "w": 50, "h": 50}
            },
            {
                "label": "dent",
                "confidence": 0.85,
                "model_source": "damage",
                "severity": "high",
                "bbox": {"x": 20, "y": 20, "w": 30, "h": 30}
            },
            {
                "label": "container_id",
                "confidence": 0.90,
                "model_source": "id",
                "container_id": "ABCD1234567",
                "bbox": {"x": 30, "y": 30, "w": 40, "h": 20}
            }
        ]
    }
    
    # Persist the analysis
    import asyncio
    inspection_id = asyncio.run(persistence_service.persist_analysis(image_data, analysis_result))
    
    # Verify detections were persisted with correct model_source
    detections = db_session.query(Detection).all()
    assert len(detections) == 3
    
    # Check model sources
    model_sources = {d.model_source for d in detections}
    assert model_sources == {"general", "damage", "id"}
    
    # Check severity is set for damage detection
    damage_detection = next(d for d in detections if d.model_source == "damage")
    assert damage_detection.severity == "high"
    
    # Check container_id is set for ID detection
    id_detection = next(d for d in detections if d.model_source == "id")
    assert id_detection.container_id == "ABCD1234567"


def test_container_upsert_creates_new_container(db_session, persistence_service):
    """Test that _upsert_container creates a new container if it doesn't exist"""
    container_id = "TEST1234567"
    
    # Verify container doesn't exist
    assert db_session.query(Container).filter(Container.id == container_id).first() is None
    
    # Call upsert
    persistence_service._upsert_container(container_id)
    db_session.commit()
    
    # Verify container was created
    container = db_session.query(Container).filter(Container.id == container_id).first()
    assert container is not None
    assert container.id == container_id
    assert container.detection_count == 1


def test_container_upsert_updates_existing_container(db_session, persistence_service):
    """Test that _upsert_container updates existing container"""
    container_id = "TEST1234567"
    
    # Create initial container
    initial_time = datetime(2024, 1, 1, 12, 0, 0)
    container = Container(
        id=container_id,
        last_seen=initial_time,
        detection_count=5
    )
    db_session.add(container)
    db_session.commit()
    
    # Call upsert
    persistence_service._upsert_container(container_id)
    db_session.commit()
    
    # Verify container was updated
    updated_container = db_session.query(Container).filter(Container.id == container_id).first()
    assert updated_container.detection_count == 6
    assert updated_container.last_seen > initial_time


def test_frame_detection_association(db_session, persistence_service):
    """Test that all detections from same frame share the same frame_id"""
    # Create a simple test image
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)
    _, encoded = cv2.imencode('.jpg', test_image)
    image_data = encoded.tobytes()
    
    # Create analysis result with multiple detections
    analysis_result = {
        "container_id": "TEST1234567",
        "status": "ok",
        "detections": [
            {
                "label": "detection1",
                "confidence": 0.95,
                "model_source": "general",
                "bbox": {"x": 10, "y": 10, "w": 50, "h": 50}
            },
            {
                "label": "detection2",
                "confidence": 0.85,
                "model_source": "damage",
                "bbox": {"x": 20, "y": 20, "w": 30, "h": 30}
            }
        ]
    }
    
    # Persist the analysis
    import asyncio
    inspection_id = asyncio.run(persistence_service.persist_analysis(image_data, analysis_result))
    
    # Verify all detections share the same frame_id
    detections = db_session.query(Detection).all()
    assert len(detections) == 2
    
    frame_ids = {d.frame_id for d in detections}
    assert len(frame_ids) == 1  # All detections share the same frame_id
    
    # Verify the frame exists
    frame_id = list(frame_ids)[0]
    frame = db_session.query(Frame).filter(Frame.id == frame_id).first()
    assert frame is not None
    assert frame.inspection_id == inspection_id


def test_all_bbox_coordinates_stored(db_session, persistence_service):
    """Test that all four bounding box coordinates are stored"""
    # Create a simple test image
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)
    _, encoded = cv2.imencode('.jpg', test_image)
    image_data = encoded.tobytes()
    
    # Create analysis result with detection
    analysis_result = {
        "container_id": "TEST1234567",
        "status": "ok",
        "detections": [
            {
                "label": "test_detection",
                "confidence": 0.95,
                "model_source": "general",
                "bbox": {"x": 10, "y": 20, "w": 30, "h": 40}
            }
        ]
    }
    
    # Persist the analysis
    import asyncio
    asyncio.run(persistence_service.persist_analysis(image_data, analysis_result))
    
    # Verify all bbox coordinates are stored
    detection = db_session.query(Detection).first()
    assert detection.bbox_x == 10
    assert detection.bbox_y == 20
    assert detection.bbox_w == 30
    assert detection.bbox_h == 40
