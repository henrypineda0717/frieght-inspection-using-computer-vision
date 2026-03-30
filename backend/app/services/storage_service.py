"""
Storage service - handles image archiving and file management
"""
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import shutil
from functools import lru_cache

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

@lru_cache(maxsize=512)
def _find_file_by_name(filename: str) -> Optional[Path]:
    if not filename:
        return None

    storage_root = settings.STORAGE_ROOT
    if not storage_root.exists():
        return None

    for candidate in storage_root.rglob(filename):
        if candidate.is_file():
            return candidate

    return None


class StorageService:
    """Service for managing image storage"""
    
    def __init__(self):
        self.storage_root = settings.STORAGE_ROOT
    
    def get_storage_path(self, container_id: str, timestamp: datetime = None) -> Path:
        """
        Generate storage path: storage/inspections/{YYYYMMDD}/{container_id}/
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        date_str = timestamp.strftime("%Y%m%d")
        path = self.storage_root / date_str / container_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def save_frame_image(
        self,
        frame_bgr: np.ndarray,
        container_id: str,
        timestamp: datetime = None,
        suffix: str = ""
    ) -> str:
        """
        Save frame image and return relative path.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        storage_path = self.get_storage_path(container_id, timestamp)
        
        # Generate filename
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"frame_{ts_str}{suffix}.jpg"
        
        full_path = storage_path / filename
        cv2.imwrite(str(full_path), frame_bgr)
        
        # Return relative path from project root
        relative_path = full_path.relative_to(settings.ROOT_DIR)
        return str(relative_path)
    
    def draw_detections_overlay(self, frame_bgr: np.ndarray, detections: List[dict]) -> np.ndarray:
        """
        Draw detections on a frame using the same visual style as RealtimeVideoProcessor.
        Handles both flat bbox fields and corners (if present).
        """
        if not detections:
            return frame_bgr

        # Helper functions
        def hex_to_bgr(hex_color: str) -> tuple:
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (b, g, r)

        def get_color(det: Dict) -> tuple:
            label = det.get('class_name', det.get('label', ''))
            model_src = det.get('model_source', '').lower()
            l = label.lower()

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

            return hex_to_bgr('#d1d5db')

        annotated = frame_bgr.copy()
        overlay = annotated.copy()
        alpha = 0.8  # or 1.0 for opaque

        for det in detections:
            color = get_color(det)
            raw_corners = det.get('corners')
            bbox = None
            x_min, y_min = None, None

            # Normalize corners if present
            if raw_corners and len(raw_corners) > 0:
                if isinstance(raw_corners[0], list) and len(raw_corners[0]) == 1 and isinstance(raw_corners[0][0], (list, tuple, np.ndarray)):
                    corners = [pt[0] for pt in raw_corners]  # flatten
                else:
                    corners = raw_corners
            else:
                corners = None

            # Draw shape
            if corners and len(corners) >= 3:
                pts = np.array(corners, dtype=np.int32).reshape((-1, 1, 2))
                cv2.fillPoly(overlay, [pts], color)
                cv2.polylines(annotated, [pts], True, color, 3, cv2.LINE_AA)

                xs = [p[0] for p in corners]
                ys = [p[1] for p in corners]
                x_min = int(min(xs))
                y_min = int(min(ys))
            else:
                # Fallback to bbox
                if 'bbox' in det and isinstance(det['bbox'], dict):
                    bbox_dict = det['bbox']
                    x = bbox_dict.get('x', 0)
                    y = bbox_dict.get('y', 0)
                    w = bbox_dict.get('w', 0)
                    h = bbox_dict.get('h', 0)
                else:
                    x = det.get('bbox_x', 0)
                    y = det.get('bbox_y', 0)
                    w = det.get('bbox_w', 0)
                    h = det.get('bbox_h', 0)
                if w == 0 or h == 0:
                    continue
                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)
                x_min, y_min = x, y
                bbox = (x, y, w, h)

            # Build label text
            model_source = det.get('model_source', '').lower()
            if model_source == 'general' and det.get('container_id'):
                container_id = det.get('container_id', '')
                iso_type = det.get('iso_type', '')
                label = container_id
                if iso_type:
                    label += f" | {iso_type}"
                text_color = (0, 255, 255)   # yellow
                bg_color = (0, 0, 0)
            else:
                class_name = det.get('class_name', det.get('label', 'unknown'))
                confidence = det.get('confidence', 0)
                label = f"{class_name} ({confidence*100:.1f}%)"
                if det.get('severity'):
                    label += f" [{det['severity']}]"
                elif det.get('track_id'):
                    label += f" [ID: {det['track_id']}]"
                text_color = (255, 255, 255)
                bg_color = (0, 0, 0)

            # Draw label background and text
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            label_x = x_min
            label_y = y_min - 10
            if label_y - th - 5 < 0:
                if bbox:
                    label_y = y_min + bbox[3] + th + 10
                elif corners:
                    y_max = int(max(ys))
                    label_y = y_max + th + 10
                else:
                    label_y = y_min + 20

            if label_x + tw + 10 > frame_bgr.shape[1]:
                label_x = frame_bgr.shape[1] - tw - 10

            cv2.rectangle(annotated,
                        (label_x - 2, label_y - th - 4),
                        (label_x + tw + 2, label_y + 4),
                        bg_color,
                        -1)
            cv2.putText(annotated, label,
                        (label_x, label_y - 5),
                        font, font_scale, text_color, thickness, cv2.LINE_AA)

        cv2.addWeighted(overlay, alpha, annotated, 1 - alpha, 0, annotated)
        return annotated

    def save_frame_with_overlay(self, frame_bgr, detections, container_id, timestamp=None):
        logger.info(f"📸 save_frame_with_overlay called for container '{container_id}' with {len(detections)} detections")
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Save original
        original_path = self.save_frame_image(frame_bgr, container_id, timestamp)
        logger.info(f"   Original saved to: {original_path}")

        # Draw and save overlay
        overlay_frame = self.draw_detections_overlay(frame_bgr, detections)
        overlay_path = self.save_frame_image(overlay_frame, container_id, timestamp, suffix="_overlay")
        
        # Check that the overlay file exists and log its size
        full_overlay_path = settings.ROOT_DIR / overlay_path
        if full_overlay_path.exists():
            logger.info(f"   ✅ Overlay saved to: {overlay_path}, size: {full_overlay_path.stat().st_size} bytes")
        else:
            logger.error(f"   ❌ Overlay file missing: {full_overlay_path}")

        return original_path, overlay_path

    def save_defect_thumbnail(
        self,
        frame_bgr: np.ndarray,
        defect: Dict[str, Any],
        container_id: str,
        timestamp: datetime = None,
        thumbnail_size: Tuple[int, int] = (128, 128)
    ) -> str:
        """
        Extract defect region from frame, resize to thumbnail, and save.
        Returns the relative path of the thumbnail.
        """
        logger.info(f"🖼️ save_defect_thumbnail called for container '{container_id}', class '{defect.get('class_name')}'")
    
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Get bounding box (support both bbox_x/y/w/h and corners)
        if 'bbox_x' in defect:
            x, y, w, h = defect['bbox_x'], defect['bbox_y'], defect['bbox_w'], defect['bbox_h']
        elif 'corners' in defect and len(defect['corners']) >= 3:
            # For polygons, use axis‑aligned bounding box
            xs = [p[0] for p in defect['corners']]
            ys = [p[1] for p in defect['corners']]
            x, y = int(min(xs)), int(min(ys))
            w, h = int(max(xs) - x), int(max(ys) - y)
        else:
            raise ValueError("Defect has no geometry")

        # Clip to frame boundaries
        h_frame, w_frame = frame_bgr.shape[:2]
        x = max(0, x)
        y = max(0, y)
        w = min(w, w_frame - x)
        h = min(h, h_frame - y)

        if w <= 0 or h <= 0:
            raise ValueError("Defect region is empty")

        # Crop and resize
        crop = frame_bgr[y:y+h, x:x+w]
        thumb = cv2.resize(crop, thumbnail_size, interpolation=cv2.INTER_AREA)

        # Build path: storage/inspections/YYYYMMDD/container_id/thumbnails/
        storage_path = self.get_storage_path(container_id, timestamp) / "thumbnails"
        storage_path.mkdir(parents=True, exist_ok=True)

        # Filename: defect_{class}_{timestamp}.jpg
        class_name = defect.get('class_name', 'unknown').replace(' ', '_')
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"defect_{class_name}_{ts_str}.jpg"
        full_path = storage_path / filename
        cv2.imwrite(str(full_path), thumb)
        if full_path.exists():
            logger.info(f"   ✅ Thumbnail successfully written, size: {full_path.stat().st_size} bytes")
        else:
            logger.error(f"   ❌ Failed to write thumbnail to {full_path}")

        # Return relative path (from project root)
        return str(full_path.relative_to(settings.ROOT_DIR))
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert a persisted storage path to the absolute file location."""
        normalized = Path(relative_path.lstrip("/"))
        storage_prefix = Path("storage") / "inspections"

        if normalized.parts[:2] == ("storage", "inspections"):
            relative_inside = normalized.relative_to(storage_prefix)
            candidate = settings.STORAGE_ROOT / relative_inside
            if candidate.exists():
                return candidate
        elif normalized.parts and normalized.parts[0] == "inspections":
            relative_inside = normalized.relative_to("inspections")
            candidate = settings.STORAGE_ROOT / relative_inside
            if candidate.exists():
                return candidate

        fallback = _find_file_by_name(normalized.name)
        if fallback:
            logger.info("Located %s by filename fallback at %s", normalized.name, fallback)
            return fallback

        legacy = settings.ROOT_DIR / normalized
        return legacy
    
    def cleanup_old_inspections(self, days_to_keep: int = None):
        """Clean up old inspection data"""
        if days_to_keep is None:
            days_to_keep = settings.RETENTION_DAYS
        
        if not self.storage_root.exists():
            return
        
        cutoff = datetime.utcnow().timestamp() - (days_to_keep * 86400)
        
        for date_dir in self.storage_root.iterdir():
            if not date_dir.is_dir():
                continue
            
            if date_dir.stat().st_mtime < cutoff:
                shutil.rmtree(date_dir)
                print(f"✓ Cleaned up: {date_dir}")