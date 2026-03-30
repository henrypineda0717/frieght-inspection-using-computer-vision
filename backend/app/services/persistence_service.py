"""
Persistence service - handles database operations for analysis results
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from typing import Dict, List, Optional, Any

import cv2
import numpy as np

from app.models import Container, Inspection, Frame, Detection
from app.services.storage_service import StorageService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PersistenceService:
    """Service for persisting analysis results to database"""
            
    def __init__(self, db: Session):
        self.db = db
        self.storage_service = StorageService()
        self._current_inspection_id = None
        self._last_saved_frame_id = None      # new
        self._last_saved_frame_number = None  # new
        self._frame_save_interval = 10        
    
    async def persist_analysis(
        self,
        image_data: bytes,
        analysis_result: Dict,
        inspection_stage: Optional[str] = None
    ) -> int:
        """
        Persist a single image analysis result.

        Returns:
            inspection_id: The ID of the created inspection
        """
        try:
            container_id = analysis_result.get("container_id", "UNKNOWN")
            container_type = analysis_result.get("container_type")

            # Ensure container exists
            container = self.db.query(Container).filter(Container.id == container_id).first()
            if not container:
                # Parse ISO 6346 fields
                owner_code = None
                category = None
                serial_number = None
                check_digit = None

                if container_id != "UNKNOWN" and len(container_id) == 11:
                    owner_code = container_id[:3]
                    category = container_id[3]
                    serial_number = container_id[4:10]
                    check_digit = int(container_id[10]) if container_id[10].isdigit() else None

                container = Container(
                    id=container_id,
                    owner_code=owner_code,
                    category=category,
                    serial_number=serial_number,
                    check_digit=check_digit,
                    iso_type=container_type,
                    last_seen=datetime.utcnow()
                )
                self.db.add(container)
                logger.debug(f"Created new container record: {container_id}")
            else:
                container.last_seen = datetime.utcnow()
                if container_type and not container.iso_type:
                    container.iso_type = container_type
                logger.debug(f"Updated existing container record: {container_id}")

            # Create inspection
            inspection = Inspection(
                container_id=container_id,
                timestamp=datetime.utcnow(),
                stage=inspection_stage,
                status=analysis_result.get("status", "ok"),
                risk_score=analysis_result.get("risk_score", 0),
                contamination_index=analysis_result.get("contamination_index", 1),
                contamination_label=analysis_result.get("contamination_label", "Low"),
                scene_caption=analysis_result.get("scene_caption"),
                anomaly_summary=analysis_result.get("anomaly_summary"),
                people_nearby=analysis_result.get("people_nearby", False),
                door_status=analysis_result.get("door_status"),
                anomalies_present=analysis_result.get("anomalies_present", False)
            )
            self.db.add(inspection)
            self.db.flush()
            logger.info(f"Created inspection record: {inspection.id}")

            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Save images
            detections_list = analysis_result.get("detections", [])
            original_path, overlay_path = self.storage_service.save_frame_with_overlay(
                frame_bgr,
                detections_list,
                container_id,
                inspection.timestamp
            )

            # Create frame
            frame = Frame(
                inspection_id=inspection.id,
                image_path=original_path,
                overlay_path=overlay_path,
                contamination_index=analysis_result.get("contamination_index", 1),
                status=analysis_result.get("status", "ok"),
                timestamp=inspection.timestamp
            )
            self.db.add(frame)
            self.db.flush()
            logger.debug(f"Created frame record: {frame.id}")

            # Create detections
            for det_dict in detections_list:
                bbox = det_dict.get("bbox")

                # Extract multi-model fields
                model_source = det_dict.get("model_source", "general")
                severity = det_dict.get("severity")  # Use provided severity from damage classifier
                detection_container_id = det_dict.get("container_id")  # Container ID from OCR

                detection = Detection(
                    frame_id=frame.id,
                    label=det_dict.get("label", ""),
                    category=det_dict.get("category"),
                    confidence=det_dict.get("confidence"),
                    bbox_x=bbox.get("x") if bbox else None,
                    bbox_y=bbox.get("y") if bbox else None,
                    bbox_w=bbox.get("w") if bbox else None,
                    bbox_h=bbox.get("h") if bbox else None,
                    model_source=model_source,
                    severity=severity if severity else self._classify_severity(det_dict),
                    defect_type=self._classify_defect_type(det_dict),
                    container_id=detection_container_id,
                )
                self.db.add(detection)

                # Update container record if container_id is present
                if detection_container_id and detection_container_id != "UNKNOWN":
                    self._upsert_container(detection_container_id)

            logger.debug(f"Created {len(detections_list)} detection records")

            self.db.commit()
            logger.info(f"Successfully persisted analysis for inspection {inspection.id}")
            return inspection.id

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error during persist_analysis: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    'operation': 'persist_analysis',
                    'container_id': analysis_result.get("container_id", "UNKNOWN"),
                    'error_type': type(e).__name__
                }
            )
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Unexpected error during persist_analysis: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    'operation': 'persist_analysis',
                    'container_id': analysis_result.get("container_id", "UNKNOWN"),
                    'error_type': type(e).__name__
                }
            )
            raise

    
    async def persist_video_analysis(
        self,
        video_results: List[Dict],
        inspection_stage: Optional[str] = None
    ) -> int:
        """
        Persist video analysis results (multiple frames).

        Returns:
            inspection_id: The ID of the created inspection
        """
        try:
            if not video_results:
                raise ValueError("No video results to persist")

            # Use first frame for inspection-level metadata
            first_result = video_results[0]
            container_id = first_result.get("container_id", "UNKNOWN")
            container_type = first_result.get("container_type")

            # Ensure container exists
            container = self.db.query(Container).filter(Container.id == container_id).first()
            if not container:
                # Parse ISO 6346 fields
                owner_code = None
                category = None
                serial_number = None
                check_digit = None

                if container_id != "UNKNOWN" and len(container_id) == 11:
                    owner_code = container_id[:3]
                    category = container_id[3]
                    serial_number = container_id[4:10]
                    check_digit = int(container_id[10]) if container_id[10].isdigit() else None

                container = Container(
                    id=container_id,
                    owner_code=owner_code,
                    category=category,
                    serial_number=serial_number,
                    check_digit=check_digit,
                    iso_type=container_type,
                    last_seen=datetime.utcnow()
                )
                self.db.add(container)
                logger.debug(f"Created new container record: {container_id}")
            else:
                container.last_seen = datetime.utcnow()
                if container_type and not container.iso_type:
                    container.iso_type = container_type
                logger.debug(f"Updated existing container record: {container_id}")

            # Aggregate inspection-level data
            max_risk = max(r.get("risk_score", 0) for r in video_results)
            max_contamination = max(r.get("contamination_index", 1) for r in video_results)
            has_alerts = any(r.get("status") == "alert" for r in video_results)

            # Create inspection
            inspection = Inspection(
                container_id=container_id,
                timestamp=datetime.utcnow(),
                stage=inspection_stage,
                status="alert" if has_alerts else "ok",
                risk_score=max_risk,
                contamination_index=max_contamination,
                contamination_label=first_result.get("contamination_label", "Low"),
                scene_caption=first_result.get("scene_caption"),
                anomaly_summary=first_result.get("anomaly_summary"),
                people_nearby=any(r.get("people_nearby", False) for r in video_results),
                door_status=first_result.get("door_status"),
                anomalies_present=any(r.get("anomalies_present", False) for r in video_results)
            )
            self.db.add(inspection)
            self.db.flush()
            logger.info(f"Created inspection record for video: {inspection.id}")

            # Process each frame
            frame_count = 0
            detection_count = 0
            all_detections = []  # Collect all detections for batch insert

            for result in video_results:
                frame_bgr = result.get("frame_bgr")
                if frame_bgr is None:
                    continue

                detections_list = result.get("detections", [])

                # Save images
                original_path, overlay_path = self.storage_service.save_frame_with_overlay(
                    frame_bgr,
                    detections_list,
                    container_id,
                    inspection.timestamp
                )

                # Create frame
                frame = Frame(
                    inspection_id=inspection.id,
                    image_path=original_path,
                    overlay_path=overlay_path,
                    contamination_index=result.get("contamination_index", 1),
                    status=result.get("status", "ok"),
                    timestamp=inspection.timestamp
                )
                self.db.add(frame)
                self.db.flush()
                frame_count += 1

                # Collect detections for batch insert
                for det_dict in detections_list:
                    bbox = det_dict.get("bbox")

                    # Extract multi-model fields
                    model_source = det_dict.get("model_source", "general")
                    severity = det_dict.get("severity")  # Use provided severity from damage classifier
                    detection_container_id = det_dict.get("container_id")  # Container ID from OCR

                    detection = Detection(
                        frame_id=frame.id,
                        label=det_dict.get("label", ""),
                        category=det_dict.get("category"),
                        confidence=det_dict.get("confidence"),
                        bbox_x=bbox.get("x") if bbox else None,
                        bbox_y=bbox.get("y") if bbox else None,
                        bbox_w=bbox.get("w") if bbox else None,
                        bbox_h=bbox.get("h") if bbox else None,
                        model_source=model_source,
                        severity=severity if severity else self._classify_severity(det_dict),
                        defect_type=self._classify_defect_type(det_dict),
                        container_id=detection_container_id,
                    )
                    all_detections.append(detection)
                    detection_count += 1

                    # Update container record if container_id is present
                    if detection_container_id and detection_container_id != "UNKNOWN":
                        self._upsert_container(detection_container_id)

            # Batch insert all detections (OPTIMIZATION: Requirement 9.2)
            # This significantly improves performance for video processing
            if all_detections:
                from app.config import settings
                batch_size = settings.VIDEO_BATCH_SIZE

                # Insert in batches to avoid memory issues with very large videos
                for i in range(0, len(all_detections), batch_size):
                    batch = all_detections[i:i + batch_size]
                    self.db.bulk_save_objects(batch)
                    logger.debug(f"Batch inserted {len(batch)} detections")

            logger.debug(f"Created {frame_count} frame records with {detection_count} detections")

            self.db.commit()
            logger.info(f"Successfully persisted video analysis for inspection {inspection.id}")
            return inspection.id

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error during persist_video_analysis: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    'operation': 'persist_video_analysis',
                    'frame_count': len(video_results) if video_results else 0,
                    'error_type': type(e).__name__
                }
            )
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Unexpected error during persist_video_analysis: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    'operation': 'persist_video_analysis',
                    'frame_count': len(video_results) if video_results else 0,
                    'error_type': type(e).__name__
                }
            )
            raise

    def persist_defect(
        self,
        frame_bgr: np.ndarray,
        defect: Dict[str, Any],
        container_id: str,
        frame_number: int,
        inspection_stage: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> int:
        """
        Save a newly detected defect with thumbnail.
        Creates a new full frame only every `_frame_save_interval` frames.
        Otherwise, attaches the defect to the most recent frame.
        """
        try:
            # 1. Ensure an inspection exists for this session
            if self._current_inspection_id is None:
                inspection = Inspection(
                    container_id=container_id,
                    timestamp=datetime.utcnow(),
                    stage=inspection_stage,
                    status='ok',
                    risk_score=0,
                    contamination_index=1,
                    contamination_label='Low',
                )
                self.db.add(inspection)
                self.db.flush()
                self._current_inspection_id = inspection.id
                logger.info(f"Created inspection {inspection.id} for video session")
                # Reset last saved frame for new inspection
                self._last_saved_frame_id = None
                self._last_saved_frame_number = None

            inspection_id = self._current_inspection_id

            # 2. Decide whether to create a new frame or reuse the last one
            create_new_frame = (
                self._last_saved_frame_id is None or
                frame_number - self._last_saved_frame_number >= self._frame_save_interval
            )

            if create_new_frame:
                # Create new frame with full images
                original_path, overlay_path = self.storage_service.save_frame_with_overlay(
                    frame_bgr,
                    [defect],
                    container_id,
                    datetime.utcnow()
                )
                frame = Frame(
                    inspection_id=inspection_id,
                    image_path=original_path,
                    overlay_path=overlay_path,
                    contamination_index=defect.get('contamination_index', 1),
                    status='ok',
                    timestamp=datetime.utcnow()
                )
                self.db.add(frame)
                self.db.flush()
                self._last_saved_frame_id = frame.id
                self._last_saved_frame_number = frame_number
                logger.debug(f"Created new frame {frame.id} for frame {frame_number}")
            else:
                # Reuse last saved frame
                frame = self.db.query(Frame).get(self._last_saved_frame_id)
                if frame is None:
                    # Fallback: create new if missing (should not happen)
                    original_path, overlay_path = self.storage_service.save_frame_with_overlay(
                        frame_bgr,
                        [defect],
                        container_id,
                        datetime.utcnow()
                    )
                    frame = Frame(
                        inspection_id=inspection_id,
                        image_path=original_path,
                        overlay_path=overlay_path,
                        contamination_index=defect.get('contamination_index', 1),
                        status='ok',
                        timestamp=datetime.utcnow()
                    )
                    self.db.add(frame)
                    self.db.flush()
                    self._last_saved_frame_id = frame.id
                    self._last_saved_frame_number = frame_number
                    logger.warning(f"Last saved frame missing; created new frame {frame.id}")
                else:
                    logger.debug(f"Reusing existing frame {frame.id} for defect at frame {frame_number}")

            # 3. Save thumbnail (always)
            thumb_path = self.storage_service.save_defect_thumbnail(
                frame_bgr, defect, container_id, datetime.utcnow()
            )

            # 4. Create detection record
            bbox = defect.get('bbox') or {}
            detection = Detection(
                frame_id=frame.id,
                label=defect.get('label') or defect.get('class_name', ''),
                category=defect.get('category'),
                confidence=defect.get('confidence'),
                bbox_x=bbox.get('x') if bbox else defect.get('bbox_x'),
                bbox_y=bbox.get('y') if bbox else defect.get('bbox_y'),
                bbox_w=bbox.get('w') if bbox else defect.get('bbox_w'),
                bbox_h=bbox.get('h') if bbox else defect.get('bbox_h'),
                model_source=defect.get('model_source', 'general'),
                severity=defect.get('severity') or self._classify_severity(defect),
                defect_type=self._classify_defect_type(defect),
                container_id=defect.get('container_id'),
                track_id=defect.get('track_id'),
                thumbnail_path=thumb_path
            )
            self.db.add(detection)
            self.db.flush()

            self.db.commit()
            logger.info(f"Saved defect {defect.get('class_name')} (track {defect.get('track_id')}) for frame {frame_number} using frame {frame.id}")
            return detection.id

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to persist defect: {e}", exc_info=True)
            raise
       
    def finalize_inspection(self, final_contamination: int = None, final_status: str = None):
        """Update inspection with final aggregated data."""
        if self._current_inspection_id:
            inspection = self.db.query(Inspection).get(self._current_inspection_id)
            if final_contamination is not None:
                inspection.contamination_index = final_contamination
            if final_status is not None:
                inspection.status = final_status
            self.db.commit()
            logger.info(f"Finalized inspection {inspection.id}")

    # ---------- END NEW METHODS ----------
    
    def _classify_defect_type(self, det_dict: Dict) -> str:
        """Classify detection into defect type"""
        cat = (det_dict.get("category") or "").lower()
        label = (det_dict.get("label") or "").lower()
        
        if cat in ("dirt", "smuts", "contamination"):
            return "dirt"
        if any(word in label for word in ["dark spot", "mold", "mould", "dirt", "smuts"]):
            return "dirt"
        if cat in ("damage", "structural_damage", "dent", "hole", "crack"):
            return "damage"
        if any(word in label for word in ["dent", "buckla", "hole", "crack", "bent"]):
            return "damage"
        
        return "other"
    
    def _classify_severity(self, det_dict: Dict) -> str:
        """Classify detection severity"""
        defect_type = self._classify_defect_type(det_dict)
        
        if defect_type == "damage":
            return "high"
        elif defect_type == "dirt":
            return "medium"
        else:
            return "low"
    
    def _upsert_container(self, container_id: str) -> None:
        """
        Insert or update container record with ISO 6346 field parsing.
        If container exists, update last_seen and increment detection_count.
        If not, create new container record with parsed ISO 6346 fields.
        
        Args:
            container_id: The container ID to upsert (ISO 6346 format)
        """
        try:
            container = self.db.query(Container).filter(Container.id == container_id).first()
            
            if container:
                # Update existing container
                container.last_seen = datetime.utcnow()
                container.detection_count += 1
                logger.debug(f"Updated container {container_id}: detection_count={container.detection_count}")
            else:
                # Parse ISO 6346 fields from container ID
                owner_code = None
                category = None
                serial_number = None
                check_digit = None
                
                if container_id != "UNKNOWN" and len(container_id) == 11:
                    owner_code = container_id[:3]
                    category = container_id[3]
                    serial_number = container_id[4:10]
                    check_digit = int(container_id[10]) if container_id[10].isdigit() else None
                
                # Create new container
                container = Container(
                    id=container_id,
                    owner_code=owner_code,
                    category=category,
                    serial_number=serial_number,
                    check_digit=check_digit,
                    last_seen=datetime.utcnow(),
                    detection_count=1
                )
                self.db.add(container)
                logger.info(f"Created new container: {container_id} (owner={owner_code}, category={category})")
        except SQLAlchemyError as e:
            logger.error(
                f"Database error during container upsert: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    'operation': 'upsert_container',
                    'container_id': container_id,
                    'error_type': type(e).__name__
                }
            )
            raise
