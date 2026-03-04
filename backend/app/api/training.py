"""
Training API endpoints
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.training_service import TrainingService

router = APIRouter()


class TrainMarkingRequest(BaseModel):
    """Schema for training marking"""
    code: str
    title: str


@router.post("/marking")
async def train_marking(item: TrainMarkingRequest, db: Session = Depends(get_db)):
    """
    Train a new container marking label.
    """
    training_service = TrainingService(db)
    result = training_service.train_marking(item.code, item.title)
    return result


@router.post("/visual")
async def train_visual(
    label: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Train visual memory with a labeled image.
    """
    training_service = TrainingService(db)
    image_data = await image.read()
    
    result = training_service.train_visual(label, image_data)
    return result


@router.get("/can_train")
async def can_train(db: Session = Depends(get_db)):
    """
    Check if we have enough data to train YOLO.
    Returns current count and whether training is possible.
    """
    training_service = TrainingService(db)
    result = training_service.can_train()
    return result


@router.post("/yolo")
async def train_yolo(db: Session = Depends(get_db)):
    """
    Trigger YOLO model training.
    Requires at least 1000 images in database.
    """
    training_service = TrainingService(db)
    result = await training_service.train_yolo()
    return result
