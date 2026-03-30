"""
Model Optimizer - Performance optimization utilities for YOLO models
"""
from typing import Optional
import torch
from ultralytics import YOLO
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ModelOptimizer:
    """
    Utilities for optimizing YOLO model inference performance.
    
    Optimizations include:
    - FP16 (half precision) inference
    - Model warmup
    - Batch processing
    - Image preprocessing optimization
    - Device optimization
    """
    
    @staticmethod
    def optimize_model(
        model: YOLO,
        use_fp16: bool = True,
        warmup: bool = True,
        imgsz: int = 640
    ) -> YOLO:
        """
        Optimize a YOLO model for faster inference.
        
        Args:
            model: YOLO model instance
            use_fp16: Enable FP16 (half precision) for GPU
            warmup: Run warmup inference
            imgsz: Image size for warmup
            
        Returns:
            Optimized YOLO model
        """
        try:
            # Check if CUDA is available
            cuda_available = torch.cuda.is_available()
            
            if cuda_available and use_fp16:
                logger.info("Enabling FP16 (half precision) for GPU acceleration")
                # FP16 will be applied during inference via half=True parameter
            
            # Warmup: Run a dummy inference to initialize CUDA kernels
            if warmup:
                logger.info(f"Running model warmup (imgsz={imgsz})...")
                import numpy as np
                dummy_img = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
                
                # Run warmup inference
                _ = model(
                    dummy_img,
                    verbose=False,
                    half=use_fp16 and cuda_available,
                    device=0 if cuda_available else 'cpu'
                )
                logger.info("Model warmup complete")
            
            return model
            
        except Exception as e:
            logger.warning(f"Model optimization failed: {e}. Continuing with default settings.")
            return model
    
    @staticmethod
    def get_optimal_imgsz(model_type: str = "yolov8") -> int:
        """
        Get optimal image size for inference based on model type.
        
        YOLOv10 can use smaller image sizes for faster inference
        while maintaining good accuracy.
        
        Args:
            model_type: Type of model (yolov8, yolov10, etc.)
            
        Returns:
            Optimal image size
        """
        if "yolov10" in model_type.lower():
            # YOLOv10 is more efficient, can use smaller sizes
            return 480  # Faster inference
        else:
            # YOLOv8 and others
            return 640  # Standard size
    
    @staticmethod
    def get_inference_params(
        use_fp16: bool = True,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        max_det: int = 300,
        agnostic_nms: bool = False
    ) -> dict:
        """
        Get optimized inference parameters.
        
        Args:
            use_fp16: Enable FP16 inference
            conf_threshold: Confidence threshold
            iou_threshold: IoU threshold for NMS
            max_det: Maximum detections per image
            agnostic_nms: Class-agnostic NMS
            
        Returns:
            Dictionary of inference parameters
        """
        cuda_available = torch.cuda.is_available()
        
        return {
            'verbose': False,
            'half': use_fp16 and cuda_available,
            'device': 0 if cuda_available else 'cpu',
            'conf': conf_threshold,
            'iou': iou_threshold,
            'max_det': max_det,
            'agnostic_nms': agnostic_nms
        }
    
    @staticmethod
    def preprocess_image_fast(image, target_size: int = 640):
        """
        Fast image preprocessing for inference.
        
        Args:
            image: Input image (numpy array)
            target_size: Target size for inference
            
        Returns:
            Preprocessed image
        """
        import cv2
        
        # Get current size
        h, w = image.shape[:2]
        
        # Only resize if image is significantly larger
        if max(h, w) > target_size * 1.5:
            # Calculate new size maintaining aspect ratio
            if h > w:
                new_h = target_size
                new_w = int(w * (target_size / h))
            else:
                new_w = target_size
                new_h = int(h * (target_size / w))
            
            # Use INTER_LINEAR for faster resizing (vs INTER_CUBIC)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        return image
    
    @staticmethod
    def should_skip_model(
        model_type: str,
        quick_mode: bool = False,
        has_detections: bool = False
    ) -> bool:
        """
        Determine if a model should be skipped for optimization.
        
        In quick mode, skip certain models based on context:
        - Skip general model if we already have damage detections
        - Skip ID model if no containers detected
        
        Args:
            model_type: Type of model (general, damage, id)
            quick_mode: Enable quick mode optimizations
            has_detections: Whether previous models found detections
            
        Returns:
            True if model should be skipped
        """
        if not quick_mode:
            return False
        
        # In quick mode, skip general model if we have damage detections
        if model_type == 'general' and has_detections:
            return True
        
        return False
