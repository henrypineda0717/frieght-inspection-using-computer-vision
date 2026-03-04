"""
Analysis service - handles image/video analysis logic
"""
from typing import Dict, List, Optional
import sys
from pathlib import Path
import numpy as np
import cv2

# Calculate root directory but don't import yet
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Global variables for lazy-loaded functions
_analyze_frame_bytes = None
_video_summary_with_gpt = None
_analysis_module_loaded = False

# Import multi-model components
from app.services.model_manager import ModelManager
from app.services.detection_coordinator import DetectionCoordinator
from app.services.ocr_processor import OCRProcessor
from app.services.damage_classifier import DamageClassifier
from app.services.result_aggregator import ResultAggregator
from app.utils.logger import get_logger
from app.config import settings

logger = get_logger(__name__)


def _load_analysis_module():
    """Lazy load the analysis module to avoid circular imports"""
    global _analyze_frame_bytes, _video_summary_with_gpt, _analysis_module_loaded
    
    if _analysis_module_loaded:
        return _analyze_frame_bytes is not None
    
    _analysis_module_loaded = True
    
    try:
        print(f"🔍 Loading analysis module from: {ROOT_DIR / 'app.py'}")
        
        # Add root to path FIRST
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        
        # Import using importlib to avoid naming conflicts
        import importlib.util
        app_py_path = ROOT_DIR / 'app.py'
        
        if not app_py_path.exists():
            print(f"❌ app.py not found at {app_py_path}")
            return False
        
        spec = importlib.util.spec_from_file_location("root_app_module", app_py_path)
        root_app = importlib.util.module_from_spec(spec)
        
        # Execute the module
        spec.loader.exec_module(root_app)
        
        _analyze_frame_bytes = root_app.analyze_frame_bytes
        _video_summary_with_gpt = root_app.video_summary_with_gpt
        
        print("✅ Successfully loaded analysis functions from app.py")
        return True
        
    except Exception as e:
        print(f"❌ Error loading analysis module: {e}")
        import traceback
        traceback.print_exc()
        return False


class AnalysisService:
    """Service for analyzing images and videos"""
    
    def __init__(self, quick_mode: bool = False):
        # Don't load module here, wait until first use
        
        # Initialize multi-model components (singleton pattern ensures model reuse)
        self.model_manager = ModelManager()
        self.detection_coordinator = DetectionCoordinator(
            self.model_manager,
            use_fp16=settings.USE_FP16,
            quick_mode=quick_mode
        )
        
        self.ocr_processor = OCRProcessor(self.model_manager)
        self.damage_classifier = DamageClassifier()
        self.result_aggregator = ResultAggregator(self.ocr_processor, self.damage_classifier)
        
        logger.info(f"AnalysisService initialized with multi-model support (quick_mode={quick_mode})")
    
    async def analyze_image_multimodel(
        self,
        image_data: bytes,
        damage_sensitivity: str = "medium",
        inspection_stage: Optional[str] = None,
        view_type: Optional[str] = None 
    ) -> Dict:
        """
        Analyze a single image using multi-model YOLO detection.
        
        This method uses the ModelManager, DetectionCoordinator, and ResultAggregator
        to run all three YOLO models (general, damage, ID) on the input image,
        extract container IDs via OCR, classify damage severity, and return
        enriched detection results.
        
        Models are loaded once at application startup via the singleton ModelManager,
        ensuring efficient reuse across all requests.
        
        Args:
            image_data: Image bytes
            damage_sensitivity: Sensitivity level (not used in multi-model, kept for compatibility)
            inspection_stage: Inspection stage (pre/post)
            
        Returns:
            Dictionary with analysis results including enriched detections
        """
        # Decode image
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            logger.error("Failed to decode image")
            return self._empty_result()
        
        # Run multi-model detection
        raw_detections = self.detection_coordinator.detect_all(image,  view_type=view_type)
        
        # Enrich detections with OCR and severity
        enriched_detections = self.result_aggregator.aggregate_detections(image, raw_detections)
        
        # Select best container ID from ID detections
        # id_detections = [d for d in enriched_detections if d['model_source'] == 'id']
        # container_id = self.result_aggregator._select_best_container_id(id_detections)
        # if not container_id:
        #     container_id = "UNKNOWN"
        
        # Collect any detection that has a valid container ID (from ID or General models)
        candidate_detections = [
            d for d in enriched_detections 
            if d.get('container_id') and d['container_id'] != 'UNKNOWN'
        ]
        if candidate_detections:
            # Reuse the existing method to pick the best (highest confidence)
            container_id = self.result_aggregator._select_best_container_id(candidate_detections)
        else:
            container_id = "UNKNOWN"
        
        # Determine status based on damage detections
        damage_detections = [d for d in enriched_detections if d['model_source'] == 'damage']
        high_severity_count = sum(1 for d in damage_detections if d.get('severity') == 'high')
        status = "alert" if high_severity_count > 0 else "ok"
        
        # Calculate risk score based on damage severity
        risk_score = self._calculate_risk_score(damage_detections)
        
        # Convert detections to API format
        formatted_detections = self._format_detections_for_api(enriched_detections)
        
        # Build response
        from datetime import datetime
        result = {
            "container_id": container_id,
            "container_type": None,  # Could be enhanced with additional detection
            "status": status,
            "detections": formatted_detections,
            "timestamp": datetime.utcnow().isoformat(),
            "people_nearby": False,
            "door_status": None,
            "lock_boxes": [],
            "anomalies_present": len(damage_detections) > 0,
            "inspection_stage": inspection_stage,
            "diff": None,
            "scene_tags": [],
            "risk_score": risk_score,
            "risk_explanations": [],
            "prewash_remarks": [],
            "resolved_remarks": [],
            "contamination_index": 1,
            "contamination_label": "Low",
            "contamination_scale": [],
            "scene_caption": None,
            "semantic_people_count": None,
            "anomaly_summary": None,
            "recommended_actions": []
        }
        
        logger.info(f"Multi-model analysis complete: {len(formatted_detections)} detections, "
                   f"container_id={container_id}, status={status}")
        
        return result
    
    def _calculate_risk_score(self, damage_detections: List[Dict]) -> int:
        """Calculate risk score based on damage detections"""
        if not damage_detections:
            return 0
        
        # Count by severity
        high_count = sum(1 for d in damage_detections if d.get('severity') == 'high')
        medium_count = sum(1 for d in damage_detections if d.get('severity') == 'medium')
        low_count = sum(1 for d in damage_detections if d.get('severity') == 'low')
        
        # Calculate weighted score (0-100)
        score = min(100, high_count * 30 + medium_count * 15 + low_count * 5)
        return score
    
    def _format_detections_for_api(self, detections: List[Dict]) -> List[Dict]:
        """
        Format detections for API response.
        
        Converts internal detection format to the API schema format expected
        by the frontend and persistence layer.
        Handles reshaping of corners from (4,1,2) to (4,2) if needed.
        """
        formatted = []
        
        for det in detections:
            # Process corners: ensure they are a list of 4 points [x,y]
            raw_corners = det.get('corners')
            if raw_corners is not None:
                # Convert to numpy array and reshape to (4,2) – this flattens any extra dimension
                corners_array = np.array(raw_corners)
                corners_reshaped = corners_array.reshape(-1, 2).tolist()
            else:
                corners_reshaped = None
            
            formatted_det = {
                "label": det['class_name'],
                "category": None,  # Could be enhanced with category mapping
                "confidence": det['confidence'],
                "bbox": {
                    "x": det['bbox_x'],
                    "y": det['bbox_y'],
                    "w": det['bbox_w'],
                    "h": det['bbox_h']
                },
                "model_source": det['model_source'],
                "severity": det.get('severity'),
                "container_id": det.get('container_id'),
                "iso_type": det.get('iso_type'),  
                "corners": corners_reshaped   # Now correctly structured
            }
            formatted.append(formatted_det)
        
        return formatted
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        from datetime import datetime
        return {
            "container_id": "UNKNOWN",
            "status": "ok",
            "detections": [],
            "timestamp": datetime.utcnow().isoformat(),
            "contamination_index": 1,
            "contamination_label": "Low",
            "risk_score": 0
        }
    
    async def analyze_image(
        self,
        image_data: bytes,
        damage_sensitivity: str = "medium",
        inspection_stage: Optional[str] = None,
        vision_backend: str = "auto",
        use_vision_gpt: bool = True,
        use_text_gpt: bool = True,
        spot_mode: str = "auto"
    ) -> Dict:
        """
        Analyze a single image using YOLO + OCR + GPT.
        """
        # Lazy load the analysis module
        if not _load_analysis_module():
            return {
                "container_id": "UNKNOWN",
                "status": "ok",
                "detections": [],
                "timestamp": "",
                "contamination_index": 1,
                "contamination_label": "Low",
                "risk_score": 0
            }
        
        try:
            # Call the actual analysis function from app.py
            result = _analyze_frame_bytes(
                image_bytes=image_data,
                damage_sensitivity=damage_sensitivity,
                inspection_stage=inspection_stage,
                enable_vision_gpt=use_vision_gpt,
                enable_text_gpt=use_text_gpt,
                vision_backend=vision_backend,
                spot_mode=spot_mode
            )
            
            # Convert Pydantic model to dict
            return result.dict() if hasattr(result, 'dict') else result
            
        except Exception as e:
            print(f"❌ Error in analyze_image: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def analyze_video(
        self,
        video_data: bytes,
        filename: str,
        damage_sensitivity: str = "medium",
        inspection_stage: Optional[str] = None,
        view_type: Optional[str] = None 
    ) -> Dict:
        """
        Analyze a video file frame by frame.
        """
        # Lazy load the analysis module
        if not _load_analysis_module():
            return {
                "video_filename": filename,
                "total_frames": 0,
                "analyzed_frames": 0,
                "results": [],
                "video_summary": "Analysis not available"
            }
        
        try:
            import cv2
            import tempfile
            import os
            from pathlib import Path
            
            # Save video to temp file
            suffix = Path(filename).suffix or ".mp4"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(video_data)
            tmp.close()
            path = tmp.name
            
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                os.remove(path)
                raise Exception("Could not read video file")
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            
            results = []
            frame_index = 0
            
            seconds_between_samples = 2.0
            step = max(1, int(fps * seconds_between_samples))
            MAX_ANALYZED_FRAMES = 40
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_index % step == 0:
                    if len(results) >= MAX_ANALYZED_FRAMES:
                        break
                    
                    ok, buf = cv2.imencode(".jpg", frame)
                    if ok:
                        try:
                            resp = _analyze_frame_bytes(
                                buf.tobytes(),
                                damage_sensitivity=damage_sensitivity,
                                inspection_stage=inspection_stage,
                                enable_vision_gpt=False,
                                enable_text_gpt=False,
                                vision_backend="none",
                                spot_mode="auto",
                            )
                            # Store frame for persistence
                            resp_dict = resp.dict() if hasattr(resp, 'dict') else resp
                            resp_dict["frame_bgr"] = frame
                            results.append(resp_dict)
                        except Exception as e:
                            print(f"Frame {frame_index}: analyze error: {e}")
                
                frame_index += 1
            
            cap.release()
            
            try:
                os.remove(path)
            except Exception:
                pass
            
            # Generate summary
            video_summary = _video_summary_with_gpt(results) if results else "No frames analyzed."
            
            return {
                "video_filename": filename,
                "total_frames": frame_count,
                "analyzed_frames": len(results),
                "results": results,
                "video_summary": video_summary
            }
            
        except Exception as e:
            print(f"❌ Error in analyze_video: {e}")
            import traceback
            traceback.print_exc()
            raise