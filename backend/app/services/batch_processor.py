"""
Batch Processor - Process multiple images in batches for better GPU utilization
"""
from typing import List, Dict, Any
import numpy as np
from ultralytics import YOLO

from app.utils.logger import get_logger
from app.utils.metrics import metrics_collector

logger = get_logger(__name__)


class BatchProcessor:
    """
    Batch processor for YOLO models to improve GPU utilization.
    Processes multiple images in a single inference call.
    """
    
    def __init__(self, model: YOLO, model_source: str, use_fp16: bool = True):
        """
        Initialize batch processor.
        
        Args:
            model: YOLO model instance
            model_source: Model identifier ('general', 'damage', 'id')
            use_fp16: Enable FP16 inference
        """
        self.model = model
        self.model_source = model_source
        self.use_fp16 = use_fp16
        
        logger.info(f"BatchProcessor initialized for {model_source} model (fp16={use_fp16})")
    
    def process_batch(
        self, 
        images: List[np.ndarray], 
        imgsz: int = 640,
        conf_threshold: float = 0.5
    ) -> List[List[Dict[str, Any]]]:
        """
        Process a batch of images.
        
        Args:
            images: List of image arrays
            imgsz: Image size for inference
            conf_threshold: Confidence threshold
            
        Returns:
            List of detection lists (one per image)
        """
        if not images:
            return []
        
        try:
            import time
            start_time = time.time()
            
            # Run batch inference
            results = self.model(
                images,
                verbose=False,
                half=self.use_fp16,
                device=None,  # Auto-detect
                imgsz=imgsz,
                conf=conf_threshold
            )
            
            inference_time = time.time() - start_time
            
            # Parse results for each image
            all_detections = []
            for result in results:
                detections = self._parse_result(result)
                all_detections.append(detections)
            
            # Log metrics
            total_detections = sum(len(d) for d in all_detections)
            metrics_collector.record_inference(
                self.model_source, 
                inference_time / len(images)  # Per-image time
            )
            metrics_collector.record_detections(self.model_source, total_detections)
            
            logger.info(
                f"Batch processed {len(images)} images: "
                f"{total_detections} detections in {inference_time*1000:.1f}ms "
                f"({inference_time/len(images)*1000:.1f}ms per image)"
            )
            
            return all_detections
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            # Return empty results for all images
            return [[] for _ in images]
    
    def _parse_result(self, result) -> List[Dict[str, Any]]:
        """
        Parse YOLO result into detection dictionaries.
        
        Args:
            result: YOLO result object
            
        Returns:
            List of detection dictionaries
        """
        detections = []
        
        if result.boxes is None or len(result.boxes) == 0:
            return detections
        
        boxes = result.boxes.xyxy.cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy().astype(int)
        
        for box, conf, cls_id in zip(boxes, confidences, class_ids):
            x1, y1, x2, y2 = box
            
            detection = {
                'class_id': int(cls_id),
                'class_name': result.names[cls_id],
                'confidence': float(conf),
                'bbox_x': int(x1),
                'bbox_y': int(y1),
                'bbox_w': int(x2 - x1),
                'bbox_h': int(y2 - y1),
                'model_source': self.model_source
            }
            
            detections.append(detection)
        
        return detections
