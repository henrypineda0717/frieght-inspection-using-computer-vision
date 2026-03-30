"""
Training service - handles model training operations
"""
import subprocess
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.frame import Frame


class TrainingService:
    """Service for training models"""
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def get_training_data_count(self) -> int:
        """
        Get the count of frames in database (training data).
        """
        if not self.db:
            return 0
        
        try:
            count = self.db.query(func.count(Frame.id)).scalar()
            return count or 0
        except Exception as e:
            print(f"Error getting training data count: {e}")
            return 0
    
    def can_train(self) -> Dict:
        """
        Check if we have enough data to train YOLO.
        Requires at least 1000 images in database.
        """
        count = self.get_training_data_count()
        can_train = count >= 1000
        
        return {
            "can_train": can_train,
            "current_count": count,
            "required_count": 1000,
            "message": f"You have {count} images. Need 1000+ to train." if not can_train else f"Ready to train with {count} images!"
        }
    
    def train_marking(self, code: str, title: str) -> Dict:
        """
        Train a new container marking label.
        """
        # TODO: Implement marking training logic
        return {
            "success": True,
            "message": f"Marking {code} trained successfully",
            "code": code,
            "title": title
        }
    
    def train_visual(self, label: str, image_data: bytes) -> Dict:
        """
        Train visual memory with a labeled image.
        """
        # TODO: Implement visual memory training logic
        return {
            "success": True,
            "message": f"Visual memory trained for label: {label}",
            "label": label
        }
    
    async def train_yolo(self) -> Dict:
        """
        Trigger YOLO model training.
        Only works if we have 1000+ images in database.
        """
        # Check if we have enough data
        check = self.can_train()
        if not check["can_train"]:
            return {
                "success": False,
                "message": check["message"],
                "current_count": check["current_count"],
                "required_count": check["required_count"]
            }
        
        try:
            result = subprocess.run(
                ["python", "scripts/train_yolo.py"],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "YOLO training completed successfully",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "message": "YOLO training failed",
                    "error": result.stderr
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "YOLO training timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"YOLO training error: {str(e)}"
            }
