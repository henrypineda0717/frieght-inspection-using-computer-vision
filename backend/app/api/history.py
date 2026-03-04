"""
History and traceability API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import io

from app.database import get_db
from app.schemas.inspection import (
    InspectionSummary,
    InspectionDetail,
    UpdateMetadataRequest
)
from app.schemas.container import ContainerResponse
from app.services.history_service import HistoryService

# Try to import report service, but make it optional
try:
    from app.services.report_service import ReportService
    REPORT_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Report service not available: {e}")
    REPORT_SERVICE_AVAILABLE = False
    ReportService = None

router = APIRouter()


@router.get("/", response_model=dict)
async def get_inspection_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    container_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of past inspections with filtering.
    """
    history_service = HistoryService(db)
    
    return history_service.get_inspections(
        page=page,
        page_size=page_size,
        container_id=container_id,
        status=status,
        stage=stage,
        search=search
    )


@router.get("/{inspection_id}", response_model=InspectionDetail)
async def get_inspection_detail(
    inspection_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific inspection.
    """
    history_service = HistoryService(db)
    
    inspection = history_service.get_inspection_detail(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    return inspection


@router.get("/containers/", response_model=List[ContainerResponse])
async def get_containers(
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get list of containers with inspection counts.
    """
    history_service = HistoryService(db)
    return history_service.get_containers(search=search, limit=limit)


@router.patch("/{inspection_id}/metadata")
async def update_inspection_metadata(
    inspection_id: int,
    data: UpdateMetadataRequest,
    db: Session = Depends(get_db)
):
    """
    Update inspection metadata (manual override for OCR corrections).
    """
    history_service = HistoryService(db)
    
    result = history_service.update_metadata(inspection_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    return result


@router.delete("/{inspection_id}")
async def delete_inspection(
    inspection_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete an inspection and all associated data.
    """
    history_service = HistoryService(db)
    
    success = history_service.delete_inspection(inspection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    return {"success": True, "message": f"Inspection {inspection_id} deleted"}


@router.get("/stats/summary")
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get overall system statistics.
    """
    history_service = HistoryService(db)
    return history_service.get_statistics()


@router.post("/cleanup/orphaned-containers")
async def cleanup_orphaned_containers(db: Session = Depends(get_db)):
    """
    Clean up containers that have no associated inspections.
    """
    history_service = HistoryService(db)
    return history_service.cleanup_orphaned_containers()


@router.get("/detections/", response_model=dict)
async def get_detections(
    inspection_id: Optional[int] = Query(None),
    model_source: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    container_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get detections with filtering by model_source, severity, and container_id.
    Supports multiple filter combinations.
    """
    history_service = HistoryService(db)
    
    return history_service.get_detections(
        inspection_id=inspection_id,
        model_source=model_source,
        severity=severity,
        container_id=container_id,
        page=page,
        page_size=page_size
    )


@router.get("/detections/statistics", response_model=dict)
async def get_detection_statistics(
    inspection_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get detection statistics grouped by model_source.
    """
    history_service = HistoryService(db)
    return history_service.get_detection_statistics(inspection_id=inspection_id)


@router.get("/{inspection_id}/report", response_model=dict)
async def get_inspection_report(
    inspection_id: int,
    db: Session = Depends(get_db)
):
    """
    Get inspection report with model breakdown.
    """
    history_service = HistoryService(db)
    
    report = history_service.get_inspection_report(inspection_id)
    if not report:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    return report


@router.get("/{inspection_id}/download-report")
async def download_inspection_report(
    inspection_id: int,
    db: Session = Depends(get_db)
):
    """
    Download a professional PDF report for an inspection.
    """
    if not REPORT_SERVICE_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Report generation service is not available. Please install reportlab: pip install reportlab"
        )
    
    history_service = HistoryService(db)
    report_service = ReportService()
    
    # Get inspection details
    inspection = history_service.get_inspection_detail(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    # Convert to dict for report generation
    inspection_dict = inspection.dict()
    
    # Generate PDF
    try:
        pdf_bytes = report_service.generate_inspection_report(inspection_dict)
        
        # Create filename
        container_id = inspection_dict.get('container_id', 'UNKNOWN')
        
        # Handle timestamp - convert to string if it's a datetime object
        timestamp_obj = inspection_dict.get('timestamp')
        if timestamp_obj:
            if hasattr(timestamp_obj, 'strftime'):
                # It's a datetime object
                timestamp_str = timestamp_obj.strftime('%Y%m%d_%H%M%S')
            else:
                # It's already a string
                timestamp_str = str(timestamp_obj).replace(':', '-').replace(' ', '_')
        else:
            timestamp_str = 'unknown'
        
        filename = f"Inspection_Report_{container_id}_{inspection_id}_{timestamp_str}.pdf"
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")
