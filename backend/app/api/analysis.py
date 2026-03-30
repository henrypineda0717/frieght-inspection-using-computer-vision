"""
Analysis API endpoints
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Body, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, Literal, Dict
import io
from datetime import datetime

from app.database import get_db
from app.schemas.analysis import AnalyzeResponse
from app.services.analysis_service import AnalysisService
from app.services.persistence_service import PersistenceService
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import report service
try:
    from app.services.report_service import ReportService
    REPORT_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Report service not available: {e}")
    REPORT_SERVICE_AVAILABLE = False
    ReportService = None

router = APIRouter()


@router.post("/", response_model=AnalyzeResponse)
async def analyze_image(
    damage_sensitivity: str = "medium",
    inspection_stage: Optional[Literal["pre", "post"]] = None,
    vision_backend: Literal["auto", "openai", "llava", "none"] = "auto",
    use_vision_gpt: bool = True,
    use_text_gpt: bool = True,
    spot_mode: Literal["auto", "mold_only", "off"] = "auto",
    use_multimodel: bool = True,  # NEW: Enable multi-model detection by default
    auto_save: bool = False,  # NEW: Control automatic saving to database
    quick_mode: bool = False,  # NEW: Enable quick mode for faster inference
    view_type: Optional[str] = None, 
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Analyze a single image. Optionally persist results to database.
    
    By default, uses the new multi-model YOLO detection system (general, damage, ID models).
    Set use_multimodel=False to use the legacy single-model analysis.
    Set auto_save=True to automatically save results to database (default: False).
    Set quick_mode=True to skip some models for faster inference (default: False).
    """
    analysis_service = AnalysisService(quick_mode=quick_mode)
    
    # Read image data
    image_data = await image.read()
    
    # Choose analysis method based on use_multimodel flag
    if use_multimodel:
        # Use new multi-model analysis
        result = await analysis_service.analyze_image_multimodel(
            image_data=image_data,
            damage_sensitivity=damage_sensitivity,
            inspection_stage=inspection_stage,
            view_type=view_type 
        )
    else:
        # Use legacy analysis (backward compatibility)
        result = await analysis_service.analyze_image(
            image_data=image_data,
            damage_sensitivity=damage_sensitivity,
            inspection_stage=inspection_stage,
            vision_backend=vision_backend,
            use_vision_gpt=use_vision_gpt,
            use_text_gpt=use_text_gpt,
            spot_mode=spot_mode
        )
    
    # Only persist to database if auto_save is True
    if auto_save:
        persistence_service = PersistenceService(db)
        try:
            inspection_id = await persistence_service.persist_analysis(
                image_data=image_data,
                analysis_result=result,
                inspection_stage=inspection_stage
            )
            result["inspection_id"] = inspection_id
            logger.info(f"Analysis auto-saved with inspection_id: {inspection_id}")
        except Exception as e:
            logger.error(f"Failed to persist analysis: {e}")
    else:
        logger.info("Analysis completed without saving (auto_save=False)")
    
    return AnalyzeResponse(**result)


@router.post("/video")
async def analyze_video(
    damage_sensitivity: str = "medium",
    inspection_stage: Optional[Literal["pre", "post"]] = None,
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Analyze a video file and persist results.
    """
    analysis_service = AnalysisService()
    persistence_service = PersistenceService(db)
    
    # Read video data
    video_data = await video.read()
    
    # Analyze video
    results = await analysis_service.analyze_video(
        video_data=video_data,
        filename=video.filename,
        damage_sensitivity=damage_sensitivity,
        inspection_stage=inspection_stage
    )
    
    # Persist to database
    inspection_id = None
    if results.get("results"):
        try:
            inspection_id = await persistence_service.persist_video_analysis(
                video_results=results["results"],
                inspection_stage=inspection_stage
            )
        except Exception as e:
            print(f"⚠ Failed to persist video analysis: {e}")
    
    results["inspection_id"] = inspection_id
    return results


@router.post("/analyze-video")
async def analyze_video_multimodel(
    frame_sample_rate: int = None,
    inspection_stage: Optional[Literal["pre", "post"]] = None,
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Analyze a video file using multi-model YOLO detection system.
    
    This endpoint:
    - Processes video frames at the specified sampling rate
    - Runs all three YOLO models (general, damage, ID) on each frame
    - Extracts container IDs via OCR from ID detections
    - Classifies damage severity for damage detections
    - Persists all frame detections to database
    - Returns annotated video with bounding boxes
    
    Args:
        frame_sample_rate: Process every Nth frame (default: from config)
        inspection_stage: Optional inspection stage ("pre" or "post")
        video: Uploaded video file
        db: Database session
        
    Returns:
        Streaming response with annotated video file
    """
    import tempfile
    import cv2
    from pathlib import Path
    
    from app.services.model_manager import ModelManager
    from app.services.detection_coordinator import DetectionCoordinator
    from app.services.ocr_processor import OCRProcessor
    from app.services.damage_classifier import DamageClassifier
    from app.services.result_aggregator import ResultAggregator
    from app.services.video_processor import VideoProcessor
    from app.config import settings
    
    # Use config default if not provided
    if frame_sample_rate is None:
        frame_sample_rate = settings.FRAME_SAMPLE_RATE
    
    # Initialize multi-model components (singleton pattern ensures model reuse)
    model_manager = ModelManager()
    detection_coordinator = DetectionCoordinator(model_manager)
    ocr_processor = OCRProcessor(model_manager)
    damage_classifier = DamageClassifier()
    result_aggregator = ResultAggregator(ocr_processor, damage_classifier)
    video_processor = VideoProcessor(
        detection_coordinator,
        result_aggregator,
        frame_sample_rate=frame_sample_rate
    )
    
    persistence_service = PersistenceService(db)
    
    # Save uploaded video to temporary file
    video_data = await video.read()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_input:
        tmp_input.write(video_data)
        tmp_input_path = tmp_input.name
    
    try:
        # Create temporary output video file
        with tempfile.NamedTemporaryFile(delete=False, suffix='_annotated.mp4') as tmp_output:
            tmp_output_path = tmp_output.name
        
        # Get video properties for output
        cap = cv2.VideoCapture(tmp_input_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        # Create video writer for output
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(tmp_output_path, fourcc, fps, (width, height))
        
        # Process video frames
        all_frame_data = []
        container_id = "UNKNOWN"
        
        for annotated_frame, enriched_detections, frame_number in video_processor.process_video(tmp_input_path):
            # Write annotated frame to output video
            out.write(annotated_frame)
            
            # Collect frame data for database persistence
            # Convert enriched detections to format expected by persistence service
            detections_for_db = []
            for det in enriched_detections:
                detection_dict = {
                    'label': det['class_name'],
                    'category': det['class_name'],
                    'confidence': det['confidence'],
                    'bbox': {
                        'x': det['bbox_x'],
                        'y': det['bbox_y'],
                        'w': det['bbox_w'],
                        'h': det['bbox_h']
                    },
                    'model_source': det['model_source'],
                    'severity': det.get('severity'),
                    'container_id': det.get('container_id')
                }
                detections_for_db.append(detection_dict)
                
                # Update container_id if found
                if det.get('container_id') and det['container_id'] != 'UNKNOWN':
                    container_id = det['container_id']
            
            # Store frame data for persistence
            frame_data = {
                'frame_bgr': annotated_frame,
                'detections': detections_for_db,
                'container_id': container_id,
                'frame_number': frame_number,
                'status': 'ok',
                'contamination_index': 1,
                'contamination_label': 'Low'
            }
            all_frame_data.append(frame_data)
        
        # Release video writer
        out.release()
        
        # Persist all frame detections to database
        inspection_id = None
        if all_frame_data:
            try:
                inspection_id = await persistence_service.persist_video_analysis(
                    video_results=all_frame_data,
                    inspection_stage=inspection_stage
                )
                logger.info(f"Video analysis persisted with inspection_id: {inspection_id}")
            except Exception as e:
                logger.error(f"Failed to persist video analysis: {e}")
                import traceback
                traceback.print_exc()
        
        # Read output video for response
        with open(tmp_output_path, 'rb') as f:
            output_video_data = f.read()
        
        # Clean up temporary files
        Path(tmp_input_path).unlink(missing_ok=True)
        Path(tmp_output_path).unlink(missing_ok=True)
        
        # Return annotated video
        return StreamingResponse(
            io.BytesIO(output_video_data),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename=annotated_{video.filename}",
                "X-Inspection-ID": str(inspection_id) if inspection_id else "none"
            }
        )
    
    except Exception as e:
        # Clean up temporary files on error
        Path(tmp_input_path).unlink(missing_ok=True)
        if 'tmp_output_path' in locals():
            Path(tmp_output_path).unlink(missing_ok=True)
        
        logger.error(f"Error processing video: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")


@router.post("/generate-report")
async def generate_analysis_report(
    analysis_data: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Generate a PDF report from current analysis data (not yet saved to database).
    This is used for the live analysis page to download reports immediately.
    Accepts analysis data as JSON string and optionally an image file.
    """
    if not REPORT_SERVICE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Report generation service is not available. Please install reportlab: pip install reportlab"
        )
    
    try:
        from pathlib import Path
        import tempfile
        import json
        
        # Parse JSON string
        analysis_dict = json.loads(analysis_data)
        
        report_service = ReportService()
        temp_image_path = None
        
        # Save image temporarily if provided
        if image:
            # Create temp file
            suffix = Path(image.filename).suffix if image.filename else '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await image.read()
                tmp.write(content)
                temp_image_path = Path(tmp.name)
                print(f"📸 Saved temporary image: {temp_image_path}")
        
        # Format the data for report generation
        report_data = {
            'id': 'LIVE',
            'container_id': analysis_dict.get('container_id', 'UNKNOWN'),
            'iso_type': analysis_dict.get('container_type'),
            'timestamp': analysis_dict.get('timestamp', datetime.now().isoformat()),
            'stage': analysis_dict.get('inspection_stage'),
            'status': analysis_dict.get('status', 'ok'),
            'risk_score': analysis_dict.get('risk_score', 0),
            'contamination_index': analysis_dict.get('contamination_index', 1),
            'contamination_label': analysis_dict.get('contamination_label', 'Low'),
            'scene_caption': analysis_dict.get('scene_caption'),
            'anomaly_summary': analysis_dict.get('anomaly_summary'),
            'people_nearby': analysis_dict.get('people_nearby', False),
            'door_status': analysis_dict.get('door_status'),
            'anomalies_present': analysis_dict.get('anomalies_present', False),
            'frames': []
        }
        
        # Add frame with image if available
        if analysis_dict.get('detections') or temp_image_path:
            pseudo_frame = {
                'id': 1,
                'image_path': str(temp_image_path) if temp_image_path else None,
                'overlay_path': None,
                'contamination_index': analysis_dict.get('contamination_index', 1),
                'status': analysis_dict.get('status', 'ok'),
                'timestamp': analysis_dict.get('timestamp'),
                'detections': analysis_dict.get('detections', [])
            }
            report_data['frames'] = [pseudo_frame]
        
        # Generate PDF
        pdf_bytes = report_service.generate_inspection_report(report_data)
        
        # Clean up temporary image
        if temp_image_path and temp_image_path.exists():
            try:
                temp_image_path.unlink()
                print(f"🗑️  Deleted temporary image: {temp_image_path}")
            except Exception as e:
                print(f"⚠️  Could not delete temp image: {e}")
        
        # Create filename
        container_id = report_data['container_id']
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Live_Analysis_Report_{container_id}_{timestamp_str}.pdf"
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        print(f"Error generating live analysis report: {e}")
        import traceback
        traceback.print_exc()
        
        # Clean up temp image on error
        if 'temp_image_path' in locals() and temp_image_path and temp_image_path.exists():
            try:
                temp_image_path.unlink()
            except:
                pass
        
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.post("/save-analysis")
async def save_analysis(
    analysis_data: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Save edited analysis results to database.
    
    This endpoint allows the frontend to save user-edited analysis data
    after the user has reviewed and corrected the results.
    
    Args:
        analysis_data: JSON string containing the edited analysis results
        image: The original image file
        db: Database session
        
    Returns:
        JSON with inspection_id and success status
    """
    try:
        import json
        
        # Parse the edited analysis data
        analysis_dict = json.loads(analysis_data)
        
        logger.info(f"💾 Saving edited analysis for container: {analysis_dict.get('container_id', 'UNKNOWN')}")
        
        # Read image data
        image_data = await image.read()
        
        # Extract inspection stage if provided
        inspection_stage = analysis_dict.get('inspection_stage')
        
        # Save to database
        persistence_service = PersistenceService(db)
        inspection_id = await persistence_service.persist_analysis(
            image_data=image_data,
            analysis_result=analysis_dict,
            inspection_stage=inspection_stage
        )
        
        logger.info(f"✅ Analysis saved successfully with inspection_id: {inspection_id}")
        
        return {
            "success": True,
            "inspection_id": inspection_id,
            "message": "Analysis saved successfully"
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse analysis data: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON data: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to save analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save analysis: {str(e)}"
        )


@router.post("/analyze-frame-realtime")
async def analyze_frame_realtime(
    image: UploadFile = File(...)
):
    """
    Real-time frame analysis for video streaming.
    
    This endpoint is optimized for real-time video analysis:
    - Fast inference (no GPT, no OCR unless needed)
    - Returns only detections with bounding boxes
    - No database persistence
    - Suitable for continuous video frame analysis
    
    Args:
        image: Video frame as image file
        
    Returns:
        JSON with detections only
    """
    try:
        from app.services.model_manager import ModelManager
        from app.services.detection_coordinator import DetectionCoordinator
        from app.services.ocr_processor import OCRProcessor
        from app.services.damage_classifier import DamageClassifier
        from app.services.result_aggregator import ResultAggregator
        import cv2
        import numpy as np
        
        # Read image data
        image_data = await image.read()
        
        # Decode image
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise HTTPException(status_code=400, detail="Failed to decode image")
        
        # Initialize components (singleton pattern ensures model reuse)
        model_manager = ModelManager()
        detection_coordinator = DetectionCoordinator(model_manager)
        ocr_processor = OCRProcessor(model_manager)
        damage_classifier = DamageClassifier()
        result_aggregator = ResultAggregator(ocr_processor, damage_classifier)
        
        # Run detection
        raw_detections = detection_coordinator.detect_all(frame)
        
        # Enrich detections (OCR only for ID detections)
        enriched_detections = result_aggregator.aggregate_detections(frame, raw_detections)
        
        # Format for API response
        formatted_detections = []
        for det in enriched_detections:
            formatted_det = {
                "label": det['class_name'],
                "category": det['class_name'],
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
                "corners": det.get('corners')  
            }
            formatted_detections.append(formatted_det)
        
        return {
            "detections": formatted_detections,
            "frame_processed": True
        }
        
    except Exception as e:
        logger.error(f"Real-time analysis failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze frame: {str(e)}"
        )


@router.post("/analyze-video-realtime")
async def analyze_video_realtime(
    detection_interval: int = 3,
    use_fp16: bool = True,
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Real-time video analysis with threaded pipeline and tracking.
    
    This endpoint provides optimized video processing for smooth playback:
    - Separate threads for capture, inference, and display
    - Runs detection every N frames (default: 3)
    - Uses ByteTrack for smooth tracking between detections
    - FP16 GPU acceleration for faster inference
    - Non-blocking pipeline for 25+ FPS playback
    - Continuously updating bounding boxes
    
    Args:
        detection_interval: Run detection every N frames (default: 3)
        use_fp16: Enable FP16 inference for GPU acceleration (default: True)
        video: Uploaded video file
        db: Database session
        
    Returns:
        Streaming response with annotated video file
    """
    import tempfile
    import cv2
    from pathlib import Path
    
    from app.services.model_manager import ModelManager
    from app.services.detection_coordinator import DetectionCoordinator
    from app.services.ocr_processor import OCRProcessor
    from app.services.damage_classifier import DamageClassifier
    from app.services.result_aggregator import ResultAggregator
    from app.services.video_processor_realtime import RealtimeVideoProcessor
    from app.services.persistence_service import PersistenceService
    from app.config import settings
    
    # Initialize components with FP16 support
    model_manager = ModelManager()
    detection_coordinator = DetectionCoordinator(model_manager, use_fp16=use_fp16)
    ocr_processor = OCRProcessor(model_manager)
    damage_classifier = DamageClassifier()
    result_aggregator = ResultAggregator(ocr_processor, damage_classifier)
    
    # Initialize real-time video processor
    video_processor = RealtimeVideoProcessor(
        detection_coordinator,
        result_aggregator,
        detection_interval=detection_interval,
        use_fp16=use_fp16
    )
    
    persistence_service = PersistenceService(db)
    
    # Save uploaded video to temporary file
    video_data = await video.read()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_input:
        tmp_input.write(video_data)
        tmp_input_path = tmp_input.name
    
    try:
        # Create temporary output video file
        with tempfile.NamedTemporaryFile(delete=False, suffix='_realtime.mp4') as tmp_output:
            tmp_output_path = tmp_output.name
        
        # Get video properties for output
        cap = cv2.VideoCapture(tmp_input_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        # Create video writer for output
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(tmp_output_path, fourcc, fps, (width, height))
        
        # Process video frames with real-time pipeline
        all_frame_data = []
        container_id = "UNKNOWN"
        
        logger.info("Starting real-time video processing...")
        
        for annotated_frame, enriched_detections, frame_number in video_processor.process_video(tmp_input_path):
            # Write annotated frame to output video
            out.write(annotated_frame)
            
            # Collect frame data for database persistence
            detections_for_db = []
            for det in enriched_detections:
                detection_dict = {
                    'label': det['class_name'],
                    'category': det['class_name'],
                    'confidence': det['confidence'],
                    'bbox': {
                        'x': det['bbox_x'],
                        'y': det['bbox_y'],
                        'w': det['bbox_w'],
                        'h': det['bbox_h']
                    },
                    'model_source': det['model_source'],
                    'severity': det.get('severity'),
                    'container_id': det.get('container_id')
                }
                detections_for_db.append(detection_dict)
                
                # Update container_id if found
                if det.get('container_id') and det['container_id'] != 'UNKNOWN':
                    container_id = det['container_id']
            
            # Store frame data for persistence
            frame_data = {
                'frame_bgr': annotated_frame,
                'detections': detections_for_db,
                'container_id': container_id,
                'frame_number': frame_number
            }
            all_frame_data.append(frame_data)
        
        # Release video writer
        out.release()
        
        logger.info(f"Real-time processing complete: {len(all_frame_data)} frames")
        
        # Persist to database
        inspection_id = persistence_service.save_inspection(
            container_id=container_id,
            frames=all_frame_data,
            inspection_stage=None
        )
        
        logger.info(f"Inspection saved with ID: {inspection_id}")
        
        # Return annotated video
        return FileResponse(
            tmp_output_path,
            media_type="video/mp4",
            filename=f"realtime_analysis_{inspection_id}.mp4",
            headers={
                "X-Inspection-ID": str(inspection_id),
                "X-Container-ID": container_id,
                "X-Frames-Processed": str(len(all_frame_data))
            }
        )
    
    except Exception as e:
        logger.error(f"Real-time video analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process video: {str(e)}"
        )
    
    finally:
        # Cleanup temporary files
        import os
        try:
            if os.path.exists(tmp_input_path):
                os.unlink(tmp_input_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup input file: {e}")