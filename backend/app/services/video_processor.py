"""
Video Processor - handles video frame extraction and real-time visualization
"""
from typing import Generator, Tuple, List, Dict, Any, Optional
import numpy as np
import cv2

from app.services.detection_coordinator import DetectionCoordinator
from app.services.process_realtimevideo import draw_detection as draw_detection_overlay
from app.services.result_aggregator import ResultAggregator
from app.utils.logger import get_logger
from app.config import settings

logger = get_logger(__name__)


def resolve_view_type_for_frame(
    frame_number: int,
    view_segments: Optional[List[Dict[str, Any]]],
    default_view: Optional[str]
) -> Optional[str]:
    """Return the view type that applies to a frame (if any)."""
    if view_segments:
        for segment in view_segments:
            start_frame = segment.get('start_frame', 0)
            end_frame = segment.get('end_frame', float('inf'))
            if start_frame <= frame_number <= end_frame:
                return segment.get('view_type')
    return default_view


class VideoProcessor:
    """
    Handles video frame extraction, detection processing, and visualization.
    
    This class processes video files by:
    - Extracting frames at a configurable sampling rate
    - Running multi-model detection on each sampled frame
    - Drawing bounding boxes with model-specific colors and labels
    - Yielding annotated frames for real-time display or storage
    """
    
    # Color mapping for different model sources (BGR format for OpenCV)
    MODEL_COLORS = {
        'general': (255, 0, 0),    # Blue
        'damage': (0, 0, 255),     # Red
        'id': (0, 255, 0)          # Green
    }
    
    def __init__(
        self, 
        detection_coordinator: DetectionCoordinator,
        result_aggregator: ResultAggregator,
        frame_sample_rate: int = None
    ):
        """
        Initialize VideoProcessor with dependencies.
        
        Args:
            detection_coordinator: DetectionCoordinator instance for running models
            result_aggregator: ResultAggregator instance for enriching detections
            frame_sample_rate: Process every Nth frame (default: from config)
        """
        self.detection_coordinator = detection_coordinator
        self.result_aggregator = result_aggregator
        # Use config default if not provided
        self.frame_sample_rate = frame_sample_rate if frame_sample_rate is not None else settings.FRAME_SAMPLE_RATE
        logger.info(f"VideoProcessor initialized with frame_sample_rate={self.frame_sample_rate}")
    
    def process_video(
        self, 
        video_path: str,
        view_segments: Optional[List[Dict[str, Any]]] = None,
        default_view: Optional[str] = None
    ) -> Generator[Tuple[np.ndarray, List[Dict[str, Any]], int], None, None]:
        """
        Process video frames and yield annotated frames with detections.
        
        Extracts frames from the video at the configured sampling rate,
        runs detection on each frame, and yields the frame with its detections
        and frame number for database association.
        
        Args:
            video_path: Path to the video file
            
        Yields:
            Tuple of (annotated_frame, enriched_detections, frame_number)
            
        Raises:
            ValueError: If video file cannot be opened
        """
        # Open video file
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            error_msg = f"Failed to open video file: {video_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Get video properties
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"Processing video: {total_frames} frames at {fps:.2f} FPS")
        logger.info(f"Sampling every {self.frame_sample_rate} frame(s)")
        
        frame_number = 0
        processed_count = 0
        
        try:
            while True:
                # Read next frame
                ret, frame = cap.read()
                
                if not ret:
                    # End of video
                    break
                
                # Check if this frame should be processed based on sampling rate
                if frame_number % self.frame_sample_rate == 0:
                    # Determine which models to run for this frame (interior/exterior)
                    selected_view = resolve_view_type_for_frame(frame_number, view_segments, default_view)
                    raw_detections = self.detection_coordinator.detect_all(frame, view_type=selected_view)
                    
                    # Enrich detections with OCR and severity
                    enriched_detections = self.result_aggregator.aggregate_detections(
                        frame, 
                        raw_detections
                    )
                    
                    # Draw detections on frame
                    annotated_frame = self.draw_detections(frame.copy(), enriched_detections)
                    
                    processed_count += 1
                    logger.debug(f"Processed frame {frame_number}: {len(enriched_detections)} detections")
                    
                    # Yield annotated frame with detections and frame number
                    yield annotated_frame, enriched_detections, frame_number
                
                frame_number += 1
        
        finally:
            # Release video capture
            cap.release()
            logger.info(f"Video processing complete: {processed_count}/{total_frames} frames processed")
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Delegate to the shared helper so video rendering stays consistent."""
        return draw_detection_overlay(frame, detections)
    
    def _format_label(self, detection: Dict[str, Any]) -> str:
        """
        Format detection label with class name, confidence, and model-specific info.
        
        Label format:
        - General: "class_name (confidence%)"
        - Damage: "class_name (confidence%) [severity]"
        - ID: "class_name (confidence%) [container_id]"
        
        Args:
            detection: Enriched detection dictionary
            
        Returns:
            Formatted label string
        """
        class_name = detection['class_name']
        confidence = detection['confidence'] * 100  # Convert to percentage
        model_source = detection['model_source']
        
        # Base label with class and confidence
        label = f"{class_name} ({confidence:.1f}%)"
        
        # Add severity for damage detections
        if model_source == 'damage' and detection.get('severity'):
            severity = detection['severity']
            label += f" [{severity}]"
        
        # Add container ID for ID detections
        elif model_source == 'id' and detection.get('container_id'):
            container_id = detection['container_id']
            label += f" [{container_id}]"
        
        return label
