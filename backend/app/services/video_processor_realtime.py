"""
Real-time Video Processor with Threading and Tracking
Optimized for smooth 25+ FPS playback with continuously updating bounding boxes
"""
from typing import Generator, Tuple, List, Dict, Any, Optional
import numpy as np
import cv2
import threading
import queue
import time
from collections import deque, Counter

from app.services.detection_coordinator import DetectionCoordinator
from app.services.result_aggregator import ResultAggregator
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RealtimeVideoProcessor:
    """
    High-performance video processor with producer-consumer architecture.
    
    Features:
    - Separate threads for frame capture, inference, and display
    - Runs detection every N frames with ByteTrack for intermediate frames
    - Non-blocking pipeline for smooth 25+ FPS playback
    - Command queue for dynamic view type changes, pause/resume
    - FPS monitoring and queue size tracking
    - GPU-optimized inference with FP16 support
    - **Synchronized global pause** – all threads stop when paused
    - **Stable container ID extraction** using voting over recent frames
    - **Contamination index** computed from damage severity (1-9 scale)
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
        detection_interval: int = 3,
        max_queue_size: int = 30,
        use_fp16: bool = True,
        initial_view_type: Optional[str] = None,
        video_path: Optional[str] = None,          # added for convenience
    ):
        """
        Initialize RealtimeVideoProcessor with threading support.
        
        Args:
            detection_coordinator: DetectionCoordinator instance
            result_aggregator: ResultAggregator instance
            detection_interval: Run detection every N frames
            max_queue_size: Maximum frames in queues
            use_fp16: Enable FP16 inference
            initial_view_type: Initial view type (exterior/interior)
            video_path: Path to the video file (can be set later)
        """
        self.detection_coordinator = detection_coordinator
        self.result_aggregator = result_aggregator
        self.detection_interval = detection_interval
        self.max_queue_size = max_queue_size
        self.use_fp16 = use_fp16
        self.current_view_type = initial_view_type
        self._view_type_lock = threading.Lock()
        self.video_path = video_path
        
        # Thread-safe queues
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.detection_queue = queue.Queue(maxsize=max_queue_size)
        self.result_queue = queue.Queue(maxsize=max_queue_size)
        
        # Thread control
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()      # Global pause for all threads
        self.threads = []
        
        # Performance tracking
        self.fps_tracker = deque(maxlen=30)
        self.last_fps_log = time.time()
        
        # Tracking state
        self.current_detections = []         
        self._detections_lock = threading.Lock()
        self.tracker = None                   
        self.tracked_id_to_last_det = {}       
        
        # Class ID mapping (populate from coordinator if needed)
        self._id_to_class = self._get_class_mapping()

        # Stable container ID extraction
        self.container_id_history = deque(maxlen=10)   # last 10 frames' IDs
        self.stable_container_id = "UNKNOWN"
        
        logger.info(
            f"RealtimeVideoProcessor initialized: "
            f"detection_interval={detection_interval}, "
            f"max_queue_size={max_queue_size}, "
            f"use_fp16={use_fp16}, "
            f"initial_view_type={initial_view_type}"
        )
    
    def _get_class_mapping(self) -> Dict[int, str]:
        """Retrieve class ID to name mapping from detection coordinator."""
        # In a real implementation, query the coordinator for class names.
        # For now, return a placeholder.
        return {0: 'unknown'}
    
    def _init_tracker(self):
        """Initialize ByteTrack tracker for smooth tracking between detections."""
        try:
            from boxmot import BYTETracker
            self.tracker = BYTETracker(
                track_thresh=0.25,
                track_buffer=30,
                match_thresh=0.8,
                frame_rate=30
            )
            logger.info("ByteTrack tracker initialized")
        except ImportError:
            logger.warning(
                "boxmot not installed. Install with: pip install boxmot"
                "\nFalling back to detection-only mode (no tracking)"
            )
            self.tracker = None
    
    def set_view_type(self, view_type: str):
        """Thread‑safe update of view type."""
        with self._view_type_lock:
            self.current_view_type = view_type
            logger.debug(f"View type set to: {view_type}")
    
    def get_view_type(self) -> Optional[str]:
        """Thread‑safe getter for view type."""
        with self._view_type_lock:
            return self.current_view_type
    
    def pause(self):
        """Pause processing – all threads will stop their work."""
        self.pause_event.set()
        logger.info(">>> Processor paused <<<")

    def resume(self):
        """Resume processing – threads will continue."""
        self.pause_event.clear()
        logger.info(">>> Processor resumed <<<")

    def stop(self):
        """Stop processing completely."""
        self.stop_event.set()
        logger.info(">>> Processor stopped <<<")
    
    def get_current_detections(self) -> List[Dict[str, Any]]:
        """Thread‑safe getter for latest detections (used by polling endpoint)."""
        with self._detections_lock:
            return self.current_detections.copy()
    
    def get_current_summary(self) -> Dict[str, Any]:
        """
        Compute aggregated statistics from the latest detections.
        Returns a dictionary with:
        - container_id (stabilized)
        - status (alert/ok)
        - total_defects
        - high/medium/low severity counts
        - risk_score (0-100)
        - contamination_index (1-9)
        """
        with self._detections_lock:
            dets = self.current_detections.copy()

        # Separate damage detections
        damage_dets = [d for d in dets if d.get('model_source', '').lower() == 'damage']

        # Severity counts
        high = sum(1 for d in damage_dets if d.get('severity') == 'high')
        medium = sum(1 for d in damage_dets if d.get('severity') == 'medium')
        low = sum(1 for d in damage_dets if d.get('severity') == 'low')

        # Risk score (same formula as AnalysisService)
        risk_score = min(100, high * 30 + medium * 15 + low * 5)

        # Map 0-100 to 1-9
        contamination_index = max(1, min(9, int(risk_score / 11.11) + 1))

        # Overall status
        status = "alert" if high > 0 else "ok"

        return {
            "container_id": self.stable_container_id,
            "status": status,
            "total_defects": len(damage_dets),
            "high_severity": high,
            "medium_severity": medium,
            "low_severity": low,
            "contamination_index": contamination_index,
            "risk_score": risk_score
        }
    
    def _extract_best_container_id(self, detections: List[Dict]) -> str:
        """
        Pick the highest‑confidence container ID from general detections.
        Returns the ID or "UNKNOWN" if none found.
        """
        candidates = []
        for d in detections:
            if d.get('model_source') == 'General' and d.get('container_id') and d['container_id'] != 'UNKNOWN':
                candidates.append((d['confidence'], d['container_id']))
        if not candidates:
            return "UNKNOWN"
        # sort by confidence descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    def _capture_frames(self):
        """
        Producer thread: Capture frames from video and push to queue.
        Honors pause_event – stops reading when paused.
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video: {self.video_path}")
            self.stop_event.set()
            return

        frame_number = 0
        try:
            while not self.stop_event.is_set():
                # 1. Check pause before attempting to read
                if self.pause_event.is_set():
                    time.sleep(0.05)          # short sleep to avoid busy‑wait
                    continue

                # 2. Read a frame (this may block)
                ret, frame = cap.read()
                if not ret:
                    break

                # 3. Check pause again immediately after read – if paused now, discard the frame
                if self.pause_event.is_set():
                    continue

                # 4. Try to push to queue with a timeout
                try:
                    self.frame_queue.put((frame, frame_number), timeout=0.5)
                    frame_number += 1
                except queue.Full:
                    logger.warning("Frame queue full, dropping frame")
                    time.sleep(0.01)

        finally:
            cap.release()
            logger.info("Capture thread stopped")

    def _run_inference(self):
        """
        Inference thread: Run detection every N frames and push results to queue.
        Honors pause_event – skips work when paused.
        """
        logger.info("Inference thread started")
        
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(0.05)
                continue

            try:
                # Get frame from queue (with timeout)
                frame, frame_number = self.frame_queue.get(timeout=1.0)
                
                # Check if we should run detection on this frame
                should_detect = (frame_number % self.detection_interval == 0)
                
                if should_detect:
                    start_time = time.time()
                    
                    # Get current view type
                    view_type = self.get_view_type()
                    
                    # Run detection (view_type is passed to coordinator)
                    raw_detections = self.detection_coordinator.detect_all(
                        frame, view_type=view_type
                    )
                    
                    # Enrich detections
                    enriched_detections = self.result_aggregator.aggregate_detections(
                        frame, raw_detections
                    )
                    
                    inference_time = time.time() - start_time
                    
                    # Push to detection queue
                    self.detection_queue.put({
                        'frame': frame,
                        'frame_number': frame_number,
                        'detections': enriched_detections,
                        'inference_time': inference_time
                    })
                    
                    logger.debug(
                        f"Frame {frame_number}: {len(enriched_detections)} detections "
                        f"in {inference_time*1000:.1f}ms"
                    )
                else:
                    # For non-detection frames, just pass through
                    self.detection_queue.put({
                        'frame': frame,
                        'frame_number': frame_number,
                        'detections': None,  # Will use tracker
                        'inference_time': 0
                    })
            
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Inference error: {e}", exc_info=True)
        
        logger.info("Inference thread stopped")
    
    def _process_results(self):
        """
        Processing thread: Apply tracking and prepare final results.
        Honors pause_event – skips work when paused.
        Also maintains stable container ID history.
        """
        logger.info("Processing thread started")
        
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(0.05)
                continue

            try:
                # Get detection result
                result = self.detection_queue.get(timeout=1.0)
                
                frame = result['frame']
                frame_number = result['frame_number']
                detections = result['detections']
                
                # Update detections and tracker
                if detections is not None:
                    # New detections available
                    new_detections = detections
                    tracked_detections = []
                    
                    # Update tracker if available
                    if self.tracker is not None and len(detections) > 0:
                        # Convert detections to tracker format [x1, y1, x2, y2, conf, class_id]
                        dets = []
                        for det in detections:
                            x1 = det['bbox_x']
                            y1 = det['bbox_y']
                            x2 = x1 + det['bbox_w']
                            y2 = y1 + det['bbox_h']
                            conf = det['confidence']
                            # Use a simple class_id mapping; can be improved
                            class_id = 0
                            dets.append([x1, y1, x2, y2, conf, class_id])
                        
                        if len(dets) > 0:
                            dets_array = np.array(dets)
                            try:
                                # Update tracker
                                tracks = self.tracker.update(dets_array, frame)
                                # tracks format: [x1, y1, x2, y2, track_id, conf, class_id, ...]
                                
                                for track in tracks:
                                    x1, y1, x2, y2, track_id, conf, class_id = track[:7]
                                    # Build detection from track
                                    track_det = {
                                        'bbox_x': int(x1),
                                        'bbox_y': int(y1),
                                        'bbox_w': int(x2 - x1),
                                        'bbox_h': int(y2 - y1),
                                        'confidence': float(conf),
                                        'class_name': self._id_to_class.get(int(class_id), 'unknown'),
                                        'model_source': 'tracked',
                                        'track_id': int(track_id)
                                    }
                                    # Merge with stored attributes if available
                                    if track_id in self.tracked_id_to_last_det:
                                        stored = self.tracked_id_to_last_det[track_id]
                                        track_det.update({
                                            'class_name': stored.get('class_name', track_det['class_name']),
                                            'severity': stored.get('severity'),
                                            'container_id': stored.get('container_id'),
                                        })
                                    else:
                                        # Store for future frames
                                        self.tracked_id_to_last_det[track_id] = track_det
                                    
                                    tracked_detections.append(track_det)
                            except Exception as e:
                                logger.warning(f"Tracker update failed: {e}")
                                tracked_detections = new_detections
                        else:
                            tracked_detections = new_detections
                    else:
                        tracked_detections = new_detections
                    
                    with self._detections_lock:
                        self.current_detections = tracked_detections
                
                else:
                    # No new detections, use tracker to update positions
                    tracked_detections = []
                    if self.tracker is not None:
                        try:
                            # Run tracker prediction with empty detections
                            tracks = self.tracker.update(np.empty((0, 6)), frame)
                            
                            for track in tracks:
                                x1, y1, x2, y2, track_id, conf, class_id = track[:7]
                                track_det = {
                                    'bbox_x': int(x1),
                                    'bbox_y': int(y1),
                                    'bbox_w': int(x2 - x1),
                                    'bbox_h': int(y2 - y1),
                                    'confidence': float(conf),
                                    'class_name': self._id_to_class.get(int(class_id), 'unknown'),
                                    'model_source': 'tracked',
                                    'track_id': int(track_id)
                                }
                                # Merge with stored attributes
                                if track_id in self.tracked_id_to_last_det:
                                    stored = self.tracked_id_to_last_det[track_id]
                                    track_det.update({
                                        'class_name': stored.get('class_name', track_det['class_name']),
                                        'severity': stored.get('severity'),
                                        'container_id': stored.get('container_id'),
                                    })
                                tracked_detections.append(track_det)
                            
                            with self._detections_lock:
                                self.current_detections = tracked_detections
                        except Exception as e:
                            logger.debug(f"Tracker prediction failed: {e}")
                    # else: no tracker, keep last detections (they will be static)
                
                # --- Update stable container ID ---
                current_id = self._extract_best_container_id(self.current_detections)
                self.container_id_history.append(current_id)
                if self.container_id_history:
                    counter = Counter(self.container_id_history)
                    self.stable_container_id = counter.most_common(1)[0][0]
                
                # Push to result queue (frame + latest detections)
                self.result_queue.put({
                    'frame': frame,
                    'frame_number': frame_number,
                    'detections': self.current_detections.copy()  # copy for thread safety
                })
            
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Processing error: {e}", exc_info=True)
        
        logger.info("Processing thread stopped")
    
    def process_video(
        self, 
        video_path: Optional[str] = None
    ) -> Generator[Tuple[np.ndarray, List[Dict[str, Any]], int], None, None]:
        """
        Process video with threaded pipeline for smooth real-time playback.
        Honors pause_event – generator will stop yielding frames when paused.
        
        Args:
            video_path: Path to the video file (overrides self.video_path if given)
            
        Yields:
            Tuple of (annotated_frame, enriched_detections, frame_number)
        """
        if video_path is not None:
            self.video_path = video_path
        
        if self.video_path is None:
            raise ValueError("No video path provided")
        
        # Initialize tracker
        self._init_tracker()
        
        # Reset state
        self.stop_event.clear()
        self.pause_event.clear()
        self.current_detections = []
        self.tracked_id_to_last_det = {}
        self.container_id_history.clear()
        self.stable_container_id = "UNKNOWN"
        
        # Clear queues
        self._clear_queues()
        
        # Start worker threads
        capture_thread = threading.Thread(
            target=self._capture_frames,
            daemon=True
        )
        
        inference_thread = threading.Thread(
            target=self._run_inference,
            daemon=True
        )
        
        processing_thread = threading.Thread(
            target=self._process_results,
            daemon=True
        )
        
        self.threads = [capture_thread, inference_thread, processing_thread]
        
        # Start all threads
        for thread in self.threads:
            thread.start()
        
        logger.info("All processing threads started")
        
        # Main loop: consume results and yield annotated frames
        frame_count = 0
        start_time = time.time()
        
        try:
            while not self.stop_event.is_set():
                # Check pause state
                if self.pause_event.is_set():
                    time.sleep(0.05)
                    continue
                
                try:
                    # Get processed result (non-blocking with timeout)
                    result = self.result_queue.get(timeout=0.1)
                    
                    frame = result['frame']
                    frame_number = result['frame_number']
                    detections = result['detections']
                    
                    # Draw detections on frame
                    annotated_frame = self.draw_detections(frame.copy(), detections)
                    
                    # Track FPS
                    frame_count += 1
                    elapsed = time.time() - start_time
                    current_fps = frame_count / elapsed if elapsed > 0 else 0
                    self.fps_tracker.append(current_fps)
                    
                    # Log FPS periodically
                    if time.time() - self.last_fps_log > 2.0:
                        avg_fps = sum(self.fps_tracker) / len(self.fps_tracker) if self.fps_tracker else 0
                        queue_sizes = (
                            self.frame_queue.qsize(),
                            self.detection_queue.qsize(),
                            self.result_queue.qsize()
                        )
                        logger.info(
                            f"FPS: {avg_fps:.1f} | "
                            f"Queues: {queue_sizes} | "
                            f"Frame: {frame_number}"
                        )
                        self.last_fps_log = time.time()
                    
                    # Yield result
                    yield annotated_frame, detections, frame_number
                
                except queue.Empty:
                    # Check if all threads are done
                    if not any(t.is_alive() for t in self.threads):
                        logger.info("All threads finished")
                        break
                    continue
        
        finally:
            # Cleanup
            self.stop_event.set()
            
            # Wait for threads to finish (increased timeout)
            for thread in self.threads:
                thread.join(timeout=5.0)
            
            # Clear queues
            self._clear_queues()
            
            # Final stats
            elapsed = time.time() - start_time
            avg_fps = frame_count / elapsed if elapsed > 0 else 0
            logger.info(
                f"Video processing complete: "
                f"{frame_count} frames in {elapsed:.1f}s "
                f"(avg {avg_fps:.1f} FPS)"
            )
    
    def _clear_queues(self):
        """Clear all queues."""
        for q in [self.frame_queue, self.detection_queue, self.result_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
    
    def draw_detections(self, frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draw detections on a frame using the same visual style as the frontend.
        Handles both flat and nested corner formats.
        """
        if not detections:
            return frame

        # Helper to convert hex to BGR
        def hex_to_bgr(hex_color: str) -> tuple:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (b, g, r)

        def get_color(det: Dict) -> tuple:
            """Replicates frontend colorForCategory logic."""
            label = det.get('class_name', '')
            model_src = det.get('model_source', '').lower()
            l = label.lower()

            # Special cases
            if any(x in l for x in ['dark spot', 'mold', 'mould', 'mögel']):
                return hex_to_bgr('#a855f7')
            if model_src == 'damage' or l.startswith('damage'):
                return hex_to_bgr('#ef4444')
            if any(x in l for x in ['dirt', 'smuts', 'looseobject', 'loose object', 'löst föremål', 'discoloration', 'missfärgning']):
                return hex_to_bgr('#eab308')
            if model_src == 'lock':
                return hex_to_bgr('#22c55e')
            if model_src in ['door', 'door_open', 'door_closed']:
                return hex_to_bgr('#e5e7eb')
            if model_src == 'human':
                return hex_to_bgr('#f9fafb')

            # Defect keyword mapping
            defect_map = {
                'crack': '#ef4444',
                'dent': '#f97316',
                'rust': '#b91c1c',
                'corrosion': '#b91c1c',
                'hole': '#dc2626',
                'dust': '#eab308',
                'powder': '#eab308',
                'oil': '#facc15',
                'stain': '#facc15',
                'nail': '#84cc16',
                'fastener': '#84cc16',
                'floor': '#3b82f6'
            }
            for keyword, col in defect_map.items():
                if keyword in l:
                    return hex_to_bgr(col)

            # Default grey
            return hex_to_bgr('#d1d5db')

        annotated = frame.copy()
        overlay = annotated.copy()
        alpha = 0.4

        for det in detections:
            color = get_color(det)
            raw_corners = det.get('corners')
            bbox = None
            x_min, y_min = None, None

            # ---- Normalize corners: if nested like [[[x,y]], ...] -> flatten to [[x,y], ...] ----
            if raw_corners and len(raw_corners) > 0:
                # Check if the first element is a list of length 1 containing a point list
                if isinstance(raw_corners[0], list) and len(raw_corners[0]) == 1 and isinstance(raw_corners[0][0], (list, tuple, np.ndarray)):
                    corners = [pt[0] for pt in raw_corners]   # flatten
                else:
                    corners = raw_corners   # already flat
            else:
                corners = None

            # ---- Draw shape (polygon or rectangle) ----
            if corners and len(corners) >= 3:
                # Convert to OpenCV format: list of (x,y) points
                pts = np.array(corners, dtype=np.int32).reshape((-1, 1, 2))
                cv2.fillPoly(overlay, [pts], color)
                cv2.polylines(annotated, [pts], True, color, 3, cv2.LINE_AA)

                xs = [p[0] for p in corners]
                ys = [p[1] for p in corners]
                x_min = int(min(xs))
                y_min = int(min(ys))

            elif 'bbox_x' in det:
                x = det['bbox_x']
                y = det['bbox_y']
                w = det['bbox_w']
                h = det['bbox_h']
                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)
                x_min, y_min = x, y
                bbox = (x, y, w, h)
            else:
                continue   # nothing to draw

            # ---- Build label text ----
            model_source = det.get('model_source', '').lower()
            if model_source == 'general' and det.get('container_id'):
                # Container ID display (yellow on black)
                container_id = det.get('container_id', '')
                iso_type = det.get('iso_type', '')
                label = container_id
                if iso_type:
                    label += f" | {iso_type}"
                text_color = (0, 255, 255)   # yellow (BGR)
                bg_color = (0, 0, 0)         # black
            else:
                class_name = det.get('class_name', 'unknown')
                confidence = det.get('confidence', 0)
                label = f"{class_name} ({confidence*100:.1f}%)"
                if det.get('severity'):
                    label += f" [{det['severity']}]"
                elif det.get('track_id'):
                    label += f" [ID: {det['track_id']}]"
                text_color = (255, 255, 255) # white
                bg_color = (0, 0, 0)         # black

            # ---- Draw label background and text ----
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            label_x = x_min
            label_y = y_min - 10
            # If above would go off-screen, place below
            if label_y - th - 5 < 0:
                if bbox:
                    label_y = y_min + bbox[3] + th + 10
                elif corners:
                    y_max = int(max(ys))
                    label_y = y_max + th + 10
                else:
                    label_y = y_min + 20

            # Keep label within frame horizontally
            if label_x + tw + 10 > frame.shape[1]:
                label_x = frame.shape[1] - tw - 10

            # Draw background rectangle
            cv2.rectangle(annotated,
                        (label_x - 2, label_y - th - 4),
                        (label_x + tw + 2, label_y + 4),
                        bg_color,
                        -1)

            # Draw text
            cv2.putText(annotated, label,
                    (label_x, label_y - 5),
                    font, font_scale, text_color, thickness, cv2.LINE_AA)

        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)
        return annotated