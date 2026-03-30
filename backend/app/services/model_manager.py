"""
Model Manager - handles loading and management of YOLOE, RF-DETR, and PaddleOCR
"""
import os
from importlib import import_module
from typing import Dict, Optional
from pathlib import Path
import time
import gc
import cv2
import numpy as np
import torch
from PIL import Image
from app.services.ocr_engine import OCREngine
from app.services.transformers_compat import ensure_transformers_prune_utils

# Force disable oneDNN for Paddle compatibility
os.environ['FLAGS_use_onednn'] = '0'

# Must happen before any AI library imports
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
os.environ['OMP_NUM_THREADS'] = '1'


import paddle # Import paddle explicitly here to "claim" the space early
paddle.utils.run_check() # Optional: verify it works before loading Torch


from ultralytics import YOLOE
from pillow_heif import register_heif_opener

ensure_transformers_prune_utils()
rfdetr_module = import_module("rfdetr")
RFDETRSegNano = rfdetr_module.RFDETRSegNano
del rfdetr_module

from app.utils.logger import get_logger
from app.utils.metrics import metrics_collector
from app.config import settings

register_heif_opener()
logger = get_logger(__name__)


class ModelManager:
    """
    Singleton responsible for managing YOLOE, RF-DETR, and PaddleOCR engine.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.yoloe_model: Optional[YOLOE] = None
        self.rt_detr_model: Optional[RFDETRSegNano] = None
        self._ocr_engine = None
        
        self.CONTAINER_CLASSES = [
            "Crack", "Crack", "Dent", "Dent and Rust", "Dust", 
            "Floor Crack", "Floor Delamination", "Floor Dust", "Floor Fungal", 
            "Floor Hole", "Floor Oil Stain", "Floor Powder", "Floor Swelling", 
            "Hole", "Nails", "Oil Stain", "Powder and Rust", "Rust", 
            "Rust and Crack", "Rust and Oil Stain", "nails on panel", "powder"
        ]
        
        self._initialized = True
        logger.info("ModelManager initialized with YOLOE, RF-DETR, and PaddleOCR")
    
    def load_models(self, warmup: bool = True) -> Dict[str, bool]:
        status = {}
        
        # 1. Load YOLOE (Rear Side)
        try:
            yoloe_path = settings.MODELS_DIR / settings.YOLOE_MODEL_PATH
#            print(yoloe_path)
 
            start_time = time.time()
 
            self.yoloe_model = YOLOE(str(yoloe_path))
 
            if warmup:
                self._warmup_yolo(self.yoloe_model, "General")
 
            status['General'] = True
 
            logger.info(f"YOLOE loaded from {yoloe_path}")
        except Exception as e:
            status['General'] = False
            logger.error(f"Failed to load YOLOE: {e}")

        # 2. Load RF-DETR (Interior Defects)
        try:
            rt_detr_path = settings.MODELS_DIR / settings.RT_DETR_MODEL_PATH
            print(rt_detr_path)
            self.rt_detr_model = RFDETRSegNano(pretrain_weights=str(rt_detr_path))
            self.rt_detr_model.optimize_for_inference()
            if warmup:
                self._warmup_rfdetr()
            status['Damage'] = True
            logger.info(f"RF-DETR loaded and optimized from {rt_detr_path}")
        except Exception as e:
            status['Damage'] = False
            logger.error(f"Failed to load RF-DETR: {e}")

        gc.collect()
        return status
    
    def _warmup_yolo(self, model: YOLOE, name: str):
        try:
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            model(dummy, verbose=False)
        except Exception as e:
            logger.warning(f"Warmup failed for {name}: {e}")

    def _warmup_rfdetr(self):
        try:
            # Create a small dummy image
            dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
            # Call .predict() instead of calling the object directly
            _ = self.rt_detr_model.predict(dummy_img, threshold=0.5)
        except Exception as e:
            logger.warning(f"Warmup failed for RF-DETR: {e}")
    
    def get_ocr_engine(self) -> Optional[OCREngine]:
        """Lazy load PaddleOCR engine"""
        if self._ocr_engine is None:
            try:
                logger.info("Initializing PaddleOCR Engine...")
                self._ocr_engine = OCREngine()
                logger.info("PaddleOCR Engine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OCR Engine: {e}")
                return None
        return self._ocr_engine

    def is_model_available(self, model_type: str) -> bool:
        mapping = {
            'General': self.yoloe_model,
            'Damage': self.rt_detr_model,
            'id': self._ocr_engine
        }
        return mapping.get(model_type) is not None
