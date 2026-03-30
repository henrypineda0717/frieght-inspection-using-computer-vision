"""
Detection Coordinator - Orchestrates YOLOE, RF-DETR, and integrated OCR processing
Now conditionally runs models based on view_type (exterior/interior)
"""
from typing import List, Dict, Any, Optional
import time
import numpy as np
import cv2

from ultralytics import YOLO
from app.utils.logger import get_logger
from app.utils.metrics import metrics_collector
from app.services.model_manager import ModelManager
from app.services.ocr_processor import OCRProcessor

logger = get_logger(__name__)

class DetectionCoordinator:    
    def __init__(self, model_manager: ModelManager, use_fp16: bool = True, 
                 conf: float = 0.1, quick_mode: bool = False):
        self.model_manager = model_manager
        self.use_fp16 = use_fp16
        self.conf = conf
        self.quick_mode = quick_mode
        self.ocr_processor = OCRProcessor(model_manager)
        logger.info(f"DetectionCoordinator initialized with quick_mode={quick_mode}")

    def detect_all(self, image: np.ndarray, imgsz: int = 640,
               view_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Run detection models based on view_type.
        
        Args:
            image: Input image (BGR)
            imgsz: Inference image size
            view_type: 'exterior', 'interior', or None (default behaviour)
        
        Returns:
            List of detection dictionaries
        """
        
        all_results = []
        
        if view_type == 'interior':
            run_yolo = False
            run_damage = True
        elif view_type == 'exterior':
            run_yolo = True
            run_damage = False
        else:
            run_yolo = self.model_manager.is_model_available('General')
            run_damage = self.model_manager.is_model_available('Damage')
        
        logger.debug(f"view_type={view_type}, run_yolo={run_yolo}, run_damage={run_damage}")
        
        if run_yolo and self.model_manager.is_model_available('General'):
            try:
                start_time = time.time()
                current_imgsz = 480 if self.quick_mode else imgsz
                rear_results = self._process_yolo(
                    self.model_manager.yoloe_model,
                    image,
                    'General',
                    imgsz=current_imgsz
                )
                self._record_metrics('yoloe_ocr', len(rear_results), start_time)
                all_results.extend(rear_results)
            except Exception as e:
                logger.error(f"Container Rear/OCR model failed: {e}", exc_info=True)

        if run_damage and self.model_manager.is_model_available('Damage'):
            try:
                start_time = time.time()
                detr_results = self._process_rf_detr(
                    self.model_manager.rt_detr_model, 
                    image, 
                    'Damage'
                )
                self._record_metrics('Damage', len(detr_results), start_time)
                all_results.extend(detr_results)
            except Exception as e:
                logger.error(f"RF-DETR model failed: {e}", exc_info=True)
                
        return all_results


    def _process_yolo(self, model: YOLO, image: np.ndarray, source: str, imgsz: int) -> List[Dict[str, Any]]:
        detections = []
        results = model.predict(image, conf=self.conf, half=self.use_fp16, imgsz=imgsz, verbose=False)
        
        if not results or results[0].masks is None:
            logger.warning("YOLOE model did not produce masks – cannot extract container region.")
            return detections

        res = results[0]
        all_candidates = []

        for i, polygon in enumerate(res.masks.xy):
            if len(polygon) < 3: continue
            
            poly_pts = polygon.astype(np.float32)
            area = cv2.contourArea(poly_pts)
            corners = self._get_four_corners(poly_pts)
            box = res.boxes[i].cpu().numpy()
            
            all_candidates.append({
                'label': model.names[int(box.cls[0])],
                'conf': float(box.conf[0]),
                'xyxy': box.xyxy[0],
                'corners': corners,
                'area': area
            })

        if not all_candidates:
            return []

        largest = max(all_candidates, key=lambda x: x['area'])

        corners = largest['corners']
        if corners.shape[0] != 4:
            logger.warning(f"Expected 4 corners, got {corners.shape[0]}. Skipping OCR.")
            ocr_data = {'container_id': 'UNKNOWN', 'iso_type': None, 'valid': False}
        else:
            corners_for_ocr = corners.reshape(4, 2).astype(np.float32)
            cropped_container = self.ocr_processor._crop_rotated(image, corners_for_ocr)
            ocr_data = self.ocr_processor.extract_id_from_crop(cropped_container)
        
        detection_dict = self._format_output(
            label=largest['label'],
            conf=largest['conf'],
            xyxy=largest['xyxy'],
            corners=largest['corners'],
            source=source
        )
        
        detection_dict.update({
            'container_id': ocr_data.get('container_id', "UNKNOWN"),
            'iso_type': ocr_data.get('iso_type'),
            'is_valid_id': ocr_data.get('valid', False)
        })

        detections.append(detection_dict)
        logger.debug(f"YOLOE processed, container_id={ocr_data.get('container_id')}")
        return detections

    def _get_four_corners(self, contour: np.ndarray) -> np.ndarray:
        """Simplifies a contour into exactly 4 points for perspective transform."""
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        
        if len(approx) != 4:
            hull = cv2.convexHull(contour)
            approx = cv2.approxPolyDP(hull, 0.02 * cv2.arcLength(hull, True), True)
            
            if len(approx) != 4:
                rect = cv2.minAreaRect(contour)
                approx = cv2.boxPoints(rect).astype(np.float32).reshape((-1, 1, 2))
        
        return approx

    def _format_output(self, label, conf, xyxy, corners, source):
        # corners may be a numpy array (from YOLOE) or a list (from RF-DETR)
        if hasattr(corners, 'tolist'):
            corners_list = corners.tolist()
        else:
            corners_list = corners  # already a list

        x1, y1, x2, y2 = xyxy
        return {
            'class_name': label,
            'confidence': conf,
            'bbox_x': int(x1),
            'bbox_y': int(y1),
            'bbox_w': int(x2 - x1),
            'bbox_h': int(y2 - y1),
            'corners': corners_list,
            'model_source': source
        }

    def _process_rf_detr(self, model: Any, image: np.ndarray, source: str) -> List[Dict[str, Any]]:
        import supervision as sv
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result = model.predict(image_rgb, threshold=self.conf)
        
        if isinstance(result, sv.Detections):
            sv_dets = result
        else:
            sv_dets = sv.Detections.from_transformers(result)

        sv_dets = sv_dets[sv_dets.confidence > self.conf]
        if sv_dets.mask is None or len(sv_dets) == 0:
            return []

        detections_list = []
        for i in range(len(sv_dets)):
            mask = sv_dets.mask[i]
            # Find contours
            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Optional: simplify contour to reduce number of points (adjust epsilon as needed)
            epsilon = 0.005 * cv2.arcLength(largest_contour, True)
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)
            
            # Convert to list of [x, y] points
            polygon = approx.reshape(-1, 2).astype(np.float32).tolist()
            
            class_id = int(sv_dets.class_id[i])
            if class_id < len(self.model_manager.CONTAINER_CLASSES):
                label = self.model_manager.CONTAINER_CLASSES[class_id]
            else:
                label = f"defect_{class_id}"

            detections_list.append(self._format_output(
                label,
                float(sv_dets.confidence[i]),
                sv_dets.xyxy[i],
                polygon,  # now a list of points
                source
            ))
        return detections_list

    def _record_metrics(self, tag: str, count: int, start_time: float):
        duration = time.time() - start_time
        metrics_collector.record_inference_time(tag, duration)
        metrics_collector.record_detections(tag, count)