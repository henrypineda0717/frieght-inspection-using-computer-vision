import os
import uuid
import cv2
import tempfile
import time
import logging
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Query, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, validator

from app.services.video_processor_realtime import RealtimeVideoProcessor
from app.services.model_manager import ModelManager
from app.services.detection_coordinator import DetectionCoordinator
from app.services.result_aggregator import ResultAggregator
from app.services.ocr_processor import OCRProcessor
from app.services.damage_classifier import DamageClassifier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video-session", tags=["Video Session"])

sessions: Dict[str, Dict[str, Any]] = {}

ALLOWED_VIEW_TYPES = {"exterior", "interior"}
ALLOWED_INSPECTION_STAGES = {"pre", "post"}

class SessionStartParams(BaseModel):
    initial_view_type: str = "exterior"
    inspection_stage: str = "pre"

    @validator("initial_view_type")
    def validate_view_type(cls, v):
        if v not in ALLOWED_VIEW_TYPES:
            raise ValueError(f"view_type must be one of {ALLOWED_VIEW_TYPES}")
        return v

    @validator("inspection_stage")
    def validate_stage(cls, v):
        if v not in ALLOWED_INSPECTION_STAGES:
            raise ValueError(f"inspection_stage must be one of {ALLOWED_INSPECTION_STAGES}")
        return v


@router.post("/start")
async def start_video_session(
    request: Request,
    video: UploadFile = File(...),
    initial_view_type: str = Query("exterior"),
    inspection_stage: str = Query("pre"),
    detection_interval: int = Query(3, ge=1, le=10),
    use_fp16: bool = Query(True),
):
    """
    Initializes a new inspection session:
    - Validates input.
    - Saves video to temporary file.
    - Initializes AI pipeline (ModelManager, OCR, DamageClassifier, etc.).
    - Creates RealtimeVideoProcessor.
    - Stores session metadata.
    - Returns session_id and stream URL.
    """
    # Validate parameters
    try:
        params = SessionStartParams(
            initial_view_type=initial_view_type,
            inspection_stage=inspection_stage
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate file type (optional but recommended)
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    tmp_path = None
    try:
        # 1. Save uploaded video to a secure temporary location
        video_data = await video.read()
        suffix = os.path.splitext(video.filename)[1] or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(video_data)
            tmp_path = tmp.name
        logger.info(f"Video saved to temporary file: {tmp_path}")

        # 2. Initialize the AI Pipeline
        try:
            # Core models
            model_manager = ModelManager()

            # Supporting services
            ocr_processor = OCRProcessor(model_manager=model_manager)  # requires model_manager
            damage_classifier = DamageClassifier()                      # no arguments needed

            # Coordinators
            detection_coordinator = DetectionCoordinator(model_manager)
            result_aggregator = ResultAggregator(
                ocr_processor=ocr_processor,
                damage_classifier=damage_classifier
            )
        except Exception as e:
            logger.error(f"Failed to initialize AI components: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="AI model initialization failed")

        # 3. Create the Processor
        processor = RealtimeVideoProcessor(
            detection_coordinator=detection_coordinator,
            result_aggregator=result_aggregator,
            detection_interval=detection_interval,
            use_fp16=use_fp16,
            initial_view_type=params.initial_view_type,
            video_path=tmp_path
        )

        # 4. Store Session Metadata
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "processor": processor,
            "video_path": tmp_path,
            "view_type": params.initial_view_type,
            "stage": params.inspection_stage,
            "created_at": time.time()
        }

        logger.info(f"Session {session_id} started with video: {video.filename}")

        # Construct the stream URL for the frontend <img> tag
        stream_url = f"/api/video-session/{session_id}/stream"

        return {
            "session_id": session_id,
            "stream_url": stream_url,
            "status": "ready"
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in start_video_session: {e}", exc_info=True)
        # Clean up temp file if it was created
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception as cleanup_err:
                logger.error(f"Failed to clean up temp file {tmp_path}: {cleanup_err}")
        raise HTTPException(status_code=500, detail="Internal Server Error during session init.")


# --- The following endpoints remain unchanged from the previous version ---

@router.get("/{session_id}/stream")
async def video_stream(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    processor = session["processor"]

    def frame_generator():
        try:
            for frame, _, _ in processor.process_video():
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ret:
                    continue
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        except Exception as e:
            logger.error(f"Stream error in session {session_id}: {e}", exc_info=True)
            raise
        finally:
            _cleanup_session_resources(session_id)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# @router.get("/{session_id}/latest-detections")
# async def get_latest_detections(session_id: str):
#     session = sessions.get(session_id)
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")
#     detections = session["processor"].get_current_detections()
#     return JSONResponse(content={
#         "session_id": session_id,
#         "detections": detections,
#         "count": len(detections)
#     })


@router.get("/{session_id}/latest-detections")
async def get_latest_detections(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    processor = session["processor"]
    detections = processor.get_current_detections()
    summary = processor.get_current_summary()

    return JSONResponse(content={
        "session_id": session_id,
        "detections": detections,
        "count": len(detections),
        "summary": summary
    })

@router.post("/{session_id}/pause")
async def pause_session(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["processor"].pause()
    return {"status": "success", "message": "Processor paused"}


@router.post("/{session_id}/resume")
async def resume_session(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["processor"].resume()
    return {"status": "success", "message": "Processor resumed"}


@router.post("/{session_id}/set-view-type")
async def set_view_type(session_id: str, view_type: str = Query(...)):
    if view_type not in ALLOWED_VIEW_TYPES:
        raise HTTPException(status_code=400, detail=f"view_type must be one of {ALLOWED_VIEW_TYPES}")
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["processor"].set_view_type(view_type)
    session["view_type"] = view_type
    return {"status": "success", "view_type": view_type}


@router.delete("/{session_id}")
async def end_session(session_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(_cleanup_session_resources, session_id)
    return {"status": "success", "message": "Session termination initiated"}


def _cleanup_session_resources(session_id: str):
    session = sessions.pop(session_id, None)
    if session:
        processor = session.get("processor")
        if processor:
            processor.stop()
        video_path = session.get("video_path")
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
                logger.info(f"Deleted temp file: {video_path}")
            except Exception as e:
                logger.error(f"Failed to delete temp file {video_path}: {e}")