"""
Storage service - handles image archiving and file management
"""
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
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
    
    def draw_detections_overlay(
        self,
        frame_bgr: np.ndarray,
        detections: List[dict]
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame.
        """
        overlay = frame_bgr.copy()
        
        for idx, det in enumerate(detections):
            bbox = det.get("bbox")
            if not bbox:
                continue
            
            x = bbox.get("x", 0)
            y = bbox.get("y", 0)
            w = bbox.get("w", 0)
            h = bbox.get("h", 0)
            
            # Color based on category
            category = (det.get("category") or "").lower()
            label = (det.get("label") or "").lower()
            
            if "dark spot" in label or "mold" in label:
                color = (247, 85, 168)  # Purple
            elif category == "damage" or label.startswith("damage"):
                color = (68, 68, 239)  # Red
            elif "dirt" in label or "loose" in label:
                color = (8, 179, 234)  # Yellow
            else:
                color = (219, 213, 209)  # Gray
            
            # Draw rectangle
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)
            
            # Draw label
            conf = det.get("confidence")
            text = f"#{idx+1} {det.get('label', '')}"
            if conf:
                text += f" ({conf*100:.1f}%)"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
            
            label_y = y - 5 if y - 5 > text_h else y + h + text_h + 5
            cv2.rectangle(overlay, (x, label_y - text_h - 2), (x + text_w + 4, label_y + 2), (0, 0, 0), -1)
            cv2.putText(overlay, text, (x + 2, label_y), font, font_scale, (255, 255, 255), thickness)
        
        return overlay
    
    def save_frame_with_overlay(
        self,
        frame_bgr: np.ndarray,
        detections: List[dict],
        container_id: str,
        timestamp: datetime = None
    ) -> Tuple[str, str]:
        """
        Save both original and overlay versions.
        
        Returns:
            (original_path, overlay_path)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Save original
        original_path = self.save_frame_image(frame_bgr, container_id, timestamp)
        
        # Draw and save overlay
        overlay_frame = self.draw_detections_overlay(frame_bgr, detections)
        overlay_path = self.save_frame_image(overlay_frame, container_id, timestamp, suffix="_overlay")
        
        return original_path, overlay_path
    
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
