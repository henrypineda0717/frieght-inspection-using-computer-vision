"""
History service - handles inspection history queries
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict

from app.models import Container, Inspection, Frame, Detection
from app.schemas.inspection import InspectionSummary, InspectionDetail, UpdateMetadataRequest
from app.schemas.frame import FrameResponse
from app.schemas.detection import DetectionResponse
from app.schemas.container import ContainerResponse


class HistoryService:
    """Service for querying inspection history"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_inspections(
        self,
        page: int = 1,
        page_size: int = 20,
        container_id: Optional[str] = None,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict:
        """
        Get paginated list of inspections with filtering.
        """
        query = self.db.query(Inspection)
        
        # Apply filters
        if container_id:
            query = query.filter(Inspection.container_id == container_id)
        
        if status:
            query = query.filter(Inspection.status == status)
        
        if stage:
            query = query.filter(Inspection.stage == stage)
        
        if search:
            query = query.filter(Inspection.container_id.contains(search))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        inspections = query.order_by(desc(Inspection.timestamp)).offset(offset).limit(page_size).all()
        
        # Build response
        items = []
        for insp in inspections:
            frame_count = len(insp.frames)
            detection_count = sum(len(frame.detections) for frame in insp.frames)
            
            items.append(InspectionSummary(
                id=insp.id,
                container_id=insp.container_id,
                iso_type=insp.container.iso_type if insp.container else None,
                timestamp=insp.timestamp,
                stage=insp.stage,
                status=insp.status,
                risk_score=insp.risk_score,
                contamination_index=insp.contamination_index,
                contamination_label=insp.contamination_label,
                frame_count=frame_count,
                detection_count=detection_count
            ))
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }
    
    def get_inspection_detail(self, inspection_id: int) -> Optional[InspectionDetail]:
        """
        Get detailed inspection information.
        """
        inspection = self.db.query(Inspection).filter(Inspection.id == inspection_id).first()
        
        if not inspection:
            return None
        
        # Build frames with detections
        frames = []
        for frame in inspection.frames:
            detections = [DetectionResponse.from_orm(det) for det in frame.detections]
            frames.append(FrameResponse(
                id=frame.id,
                image_path=frame.image_path,
                overlay_path=frame.overlay_path,
                contamination_index=frame.contamination_index,
                status=frame.status,
                timestamp=frame.timestamp,
                detections=detections
            ))
        
        return InspectionDetail(
            id=inspection.id,
            container_id=inspection.container_id,
            iso_type=inspection.container.iso_type if inspection.container else None,
            timestamp=inspection.timestamp,
            stage=inspection.stage,
            status=inspection.status,
            risk_score=inspection.risk_score,
            contamination_index=inspection.contamination_index,
            contamination_label=inspection.contamination_label,
            scene_caption=inspection.scene_caption,
            anomaly_summary=inspection.anomaly_summary,
            people_nearby=inspection.people_nearby,
            door_status=inspection.door_status,
            anomalies_present=inspection.anomalies_present,
            frames=frames
        )
    
    def get_containers(
        self,
        search: Optional[str] = None,
        limit: int = 50
    ) -> List[ContainerResponse]:
        """
        Get list of containers with inspection counts.
        """
        query = self.db.query(Container)
        
        if search:
            query = query.filter(Container.id.contains(search))
        
        containers = query.order_by(desc(Container.last_seen)).limit(limit).all()
        
        result = []
        for container in containers:
            result.append(ContainerResponse(
                id=container.id,
                iso_type=container.iso_type,
                last_seen=container.last_seen,
                inspection_count=len(container.inspections)
            ))
        
        return result
    
    def update_metadata(
        self,
        inspection_id: int,
        data: UpdateMetadataRequest
    ) -> Optional[Dict]:
        """
        Update inspection metadata (OCR override).
        """
        inspection = self.db.query(Inspection).filter(Inspection.id == inspection_id).first()
        
        if not inspection:
            return None
        
        old_container_id = inspection.container_id
        
        # Update container_id if provided
        if data.container_id and data.container_id != old_container_id:
            new_container = self.db.query(Container).filter(Container.id == data.container_id).first()
            if not new_container:
                new_container = Container(id=data.container_id, iso_type=data.iso_type)
                self.db.add(new_container)
            
            inspection.container_id = data.container_id
            inspection.container = new_container
        
        # Update iso_type if provided
        if data.iso_type and inspection.container:
            inspection.container.iso_type = data.iso_type
        
        self.db.commit()
        self.db.refresh(inspection)
        
        return {
            "success": True,
            "message": "Metadata updated successfully",
            "inspection_id": inspection_id,
            "container_id": inspection.container_id,
            "iso_type": inspection.container.iso_type if inspection.container else None
        }
    
    def delete_inspection(self, inspection_id: int) -> bool:
        """
        Delete an inspection and clean up orphaned containers.
        """
        inspection = self.db.query(Inspection).filter(Inspection.id == inspection_id).first()
        
        if not inspection:
            return False
        
        # Store container_id before deletion
        container_id = inspection.container_id
        
        # Delete the inspection (frames and detections cascade automatically)
        self.db.delete(inspection)
        self.db.commit()
        
        # Check if the container has any remaining inspections
        container = self.db.query(Container).filter(Container.id == container_id).first()
        if container:
            remaining_inspections = self.db.query(Inspection).filter(
                Inspection.container_id == container_id
            ).count()
            
            # If no inspections remain, delete the container
            if remaining_inspections == 0:
                self.db.delete(container)
                self.db.commit()
        
        return True
    
    def cleanup_orphaned_containers(self) -> Dict:
        """
        Remove containers that have no associated inspections.
        """
        # Find all containers
        all_containers = self.db.query(Container).all()
        deleted_count = 0
        
        for container in all_containers:
            inspection_count = self.db.query(Inspection).filter(
                Inspection.container_id == container.id
            ).count()
            
            if inspection_count == 0:
                self.db.delete(container)
                deleted_count += 1
        
        self.db.commit()
        
        return {
            "success": True,
            "deleted_containers": deleted_count,
            "message": f"Cleaned up {deleted_count} orphaned container(s)"
        }
    
    def get_statistics(self) -> Dict:
        """
        Get system-wide statistics.
        """
        total_inspections = self.db.query(Inspection).count()
        total_containers = self.db.query(Container).count()
        total_frames = self.db.query(Frame).count()
        total_detections = self.db.query(Detection).count()
        
        alert_count = self.db.query(Inspection).filter(Inspection.status == "alert").count()
        
        return {
            "total_inspections": total_inspections,
            "total_containers": total_containers,
            "total_frames": total_frames,
            "total_detections": total_detections,
            "alert_inspections": alert_count,
            "ok_inspections": total_inspections - alert_count
        }
    
    def get_detections(
        self,
        inspection_id: Optional[int] = None,
        model_source: Optional[str] = None,
        severity: Optional[str] = None,
        container_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict:
        """
        Get detections with filtering by model_source, severity, and container_id.
        Supports multiple filter combinations.
        """
        query = self.db.query(Detection)
        
        # Apply filters
        if inspection_id:
            # Filter by inspection_id through frame relationship
            query = query.join(Frame).join(Inspection).filter(Inspection.id == inspection_id)
        
        if model_source:
            query = query.filter(Detection.model_source == model_source)
        
        if severity:
            query = query.filter(Detection.severity == severity)
        
        if container_id:
            query = query.filter(Detection.container_id == container_id)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        detections = query.offset(offset).limit(page_size).all()
        
        # Build response
        items = [DetectionResponse.from_orm(det) for det in detections]
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }
    
    def get_detection_statistics(self, inspection_id: Optional[int] = None) -> Dict:
        """
        Get detection statistics grouped by model_source.
        """
        query = self.db.query(
            Detection.model_source,
            func.count(Detection.id).label('count')
        )
        
        # Filter by inspection if provided
        if inspection_id:
            query = query.join(Frame).join(Inspection).filter(Inspection.id == inspection_id)
        
        # Group by model_source
        results = query.group_by(Detection.model_source).all()
        
        # Build statistics
        by_model = {row.model_source: row.count for row in results}
        total = sum(by_model.values())
        
        # Get severity breakdown for damage detections
        severity_query = self.db.query(
            Detection.severity,
            func.count(Detection.id).label('count')
        ).filter(Detection.severity.isnot(None))
        
        if inspection_id:
            severity_query = severity_query.join(Frame).join(Inspection).filter(Inspection.id == inspection_id)
        
        severity_results = severity_query.group_by(Detection.severity).all()
        by_severity = {row.severity: row.count for row in severity_results}
        
        return {
            "total_detections": total,
            "by_model_source": by_model,
            "by_severity": by_severity
        }
    
    def get_inspection_report(self, inspection_id: int) -> Optional[Dict]:
        """
        Generate inspection report with model breakdown.
        """
        inspection = self.db.query(Inspection).filter(Inspection.id == inspection_id).first()
        
        if not inspection:
            return None
        
        # Get detection statistics for this inspection
        stats = self.get_detection_statistics(inspection_id=inspection_id)
        
        # Get frame count
        frame_count = len(inspection.frames)
        
        # Get unique container IDs detected
        container_ids = self.db.query(Detection.container_id).join(Frame).join(Inspection).filter(
            Inspection.id == inspection_id,
            Detection.container_id.isnot(None),
            Detection.container_id != "UNKNOWN"
        ).distinct().all()
        
        unique_containers = [cid[0] for cid in container_ids]
        
        return {
            "inspection_id": inspection_id,
            "container_id": inspection.container_id,
            "timestamp": inspection.timestamp,
            "status": inspection.status,
            "stage": inspection.stage,
            "frame_count": frame_count,
            "detection_statistics": stats,
            "detected_container_ids": unique_containers,
            "risk_score": inspection.risk_score,
            "contamination_index": inspection.contamination_index
        }
