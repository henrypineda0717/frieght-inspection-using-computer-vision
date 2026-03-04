"""
Monitoring metrics for the container inspection system
"""
import time
from typing import Dict, Optional
from collections import defaultdict
from threading import Lock
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """
    Singleton class for collecting and tracking system metrics.
    
    Tracks:
    - Model loading status at startup
    - Inference times per model
    - OCR success/failure rates
    - Detection counts by model source
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MetricsCollector, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize metrics storage"""
        if self._initialized:
            return
        
        # Model loading status
        self.model_status: Dict[str, bool] = {}
        self.model_load_time: Dict[str, float] = {}
        
        # Inference timing metrics
        self.inference_times: Dict[str, list] = defaultdict(list)
        self.inference_count: Dict[str, int] = defaultdict(int)
        
        # OCR metrics
        self.ocr_success_count: int = 0
        self.ocr_failure_count: int = 0
        self.ocr_times: list = []
        
        # Detection counts by model source
        self.detection_counts: Dict[str, int] = defaultdict(int)
        
        # System startup time
        self.startup_time: Optional[datetime] = None
        
        self._initialized = True
        logger.info("MetricsCollector initialized")
    
    def record_model_load(self, model_type: str, success: bool, load_time: float) -> None:
        """
        Record model loading status and time.
        
        Args:
            model_type: Type of model ('general', 'damage', 'id')
            success: Whether the model loaded successfully
            load_time: Time taken to load the model in seconds
        """
        self.model_status[model_type] = success
        self.model_load_time[model_type] = load_time
        
        status_str = "successfully" if success else "failed"
        logger.info(f"Model load metric: {model_type} {status_str} in {load_time:.3f}s")
    
    def record_inference_time(self, model_type: str, inference_time: float) -> None:
        """
        Record inference time for a model.
        
        Args:
            model_type: Type of model ('general', 'damage', 'id')
            inference_time: Time taken for inference in seconds
        """
        self.inference_times[model_type].append(inference_time)
        self.inference_count[model_type] += 1
        
        logger.debug(f"Inference metric: {model_type} took {inference_time:.3f}s")
    
    def record_ocr_result(self, success: bool, ocr_time: float) -> None:
        """
        Record OCR operation result and time.
        
        Args:
            success: Whether OCR extraction was successful
            ocr_time: Time taken for OCR in seconds
        """
        if success:
            self.ocr_success_count += 1
        else:
            self.ocr_failure_count += 1
        
        self.ocr_times.append(ocr_time)
        
        logger.debug(f"OCR metric: {'success' if success else 'failure'} in {ocr_time:.3f}s")
    
    def record_detections(self, model_source: str, count: int) -> None:
        """
        Record detection count for a model source.
        
        Args:
            model_source: Source model ('general', 'damage', 'id')
            count: Number of detections produced
        """
        self.detection_counts[model_source] += count
        
        logger.debug(f"Detection metric: {model_source} produced {count} detections")
    
    def set_startup_time(self, startup_time: datetime) -> None:
        """
        Record system startup time.
        
        Args:
            startup_time: Timestamp when system started
        """
        self.startup_time = startup_time
        logger.info(f"System startup time recorded: {startup_time}")
    
    def get_model_metrics(self) -> Dict:
        """
        Get model loading and inference metrics.
        
        Returns:
            Dictionary containing model status, load times, and inference statistics
        """
        metrics = {
            'model_status': self.model_status.copy(),
            'model_load_time': self.model_load_time.copy(),
            'inference_stats': {}
        }
        
        for model_type, times in self.inference_times.items():
            if times:
                metrics['inference_stats'][model_type] = {
                    'count': self.inference_count[model_type],
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'total_time': sum(times)
                }
        
        return metrics
    
    def get_ocr_metrics(self) -> Dict:
        """
        Get OCR success/failure metrics.
        
        Returns:
            Dictionary containing OCR statistics
        """
        total_ocr = self.ocr_success_count + self.ocr_failure_count
        success_rate = (self.ocr_success_count / total_ocr * 100) if total_ocr > 0 else 0.0
        
        metrics = {
            'success_count': self.ocr_success_count,
            'failure_count': self.ocr_failure_count,
            'total_count': total_ocr,
            'success_rate': success_rate
        }
        
        if self.ocr_times:
            metrics['avg_time'] = sum(self.ocr_times) / len(self.ocr_times)
            metrics['min_time'] = min(self.ocr_times)
            metrics['max_time'] = max(self.ocr_times)
        
        return metrics
    
    def get_detection_metrics(self) -> Dict:
        """
        Get detection count metrics by model source.
        
        Returns:
            Dictionary containing detection counts per model
        """
        return {
            'detection_counts': dict(self.detection_counts),
            'total_detections': sum(self.detection_counts.values())
        }
    
    def get_all_metrics(self) -> Dict:
        """
        Get all collected metrics.
        
        Returns:
            Dictionary containing all metrics
        """
        return {
            'startup_time': self.startup_time.isoformat() if self.startup_time else None,
            'models': self.get_model_metrics(),
            'ocr': self.get_ocr_metrics(),
            'detections': self.get_detection_metrics()
        }
    
    def log_summary(self) -> None:
        """Log a summary of all collected metrics"""
        logger.info("=== Metrics Summary ===")
        
        # Model metrics
        logger.info(f"Model Status: {self.model_status}")
        logger.info(f"Model Load Times: {self.model_load_time}")
        
        # Inference metrics
        for model_type, times in self.inference_times.items():
            if times:
                avg_time = sum(times) / len(times)
                logger.info(
                    f"Inference {model_type}: count={self.inference_count[model_type]}, "
                    f"avg={avg_time:.3f}s, min={min(times):.3f}s, max={max(times):.3f}s"
                )
        
        # OCR metrics
        total_ocr = self.ocr_success_count + self.ocr_failure_count
        if total_ocr > 0:
            success_rate = self.ocr_success_count / total_ocr * 100
            logger.info(
                f"OCR: success={self.ocr_success_count}, failure={self.ocr_failure_count}, "
                f"rate={success_rate:.1f}%"
            )
        
        # Detection metrics
        logger.info(f"Detection Counts: {dict(self.detection_counts)}")
        logger.info(f"Total Detections: {sum(self.detection_counts.values())}")
        
        logger.info("======================")


# Global metrics collector instance
metrics_collector = MetricsCollector()
