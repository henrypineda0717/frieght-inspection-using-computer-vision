"""
Metrics API endpoints
"""
from fastapi import APIRouter
from typing import Dict

from app.utils.metrics import metrics_collector
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/metrics", response_model=Dict)
async def get_metrics():
    """
    Get all collected system metrics.
    
    Returns metrics for:
    - Model loading status and times
    - Inference times per model
    - OCR success/failure rates
    - Detection counts by model source
    """
    try:
        metrics = metrics_collector.get_all_metrics()
        logger.info("Metrics retrieved successfully")
        return metrics
    except Exception as e:
        logger.error(f"Failed to retrieve metrics: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/metrics/models", response_model=Dict)
async def get_model_metrics():
    """
    Get model-specific metrics.
    
    Returns:
    - Model loading status
    - Model load times
    - Inference statistics per model
    """
    try:
        metrics = metrics_collector.get_model_metrics()
        logger.debug("Model metrics retrieved")
        return metrics
    except Exception as e:
        logger.error(f"Failed to retrieve model metrics: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/metrics/ocr", response_model=Dict)
async def get_ocr_metrics():
    """
    Get OCR-specific metrics.
    
    Returns:
    - OCR success/failure counts
    - OCR success rate
    - OCR timing statistics
    """
    try:
        metrics = metrics_collector.get_ocr_metrics()
        logger.debug("OCR metrics retrieved")
        return metrics
    except Exception as e:
        logger.error(f"Failed to retrieve OCR metrics: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/metrics/detections", response_model=Dict)
async def get_detection_metrics():
    """
    Get detection count metrics.
    
    Returns:
    - Detection counts per model source
    - Total detection count
    """
    try:
        metrics = metrics_collector.get_detection_metrics()
        logger.debug("Detection metrics retrieved")
        return metrics
    except Exception as e:
        logger.error(f"Failed to retrieve detection metrics: {e}", exc_info=True)
        return {"error": str(e)}


@router.post("/metrics/summary")
async def log_metrics_summary():
    """
    Log a summary of all metrics to the application logs.
    
    This endpoint triggers a comprehensive metrics summary to be written
    to the logs for monitoring and debugging purposes.
    """
    try:
        metrics_collector.log_summary()
        return {"status": "success", "message": "Metrics summary logged"}
    except Exception as e:
        logger.error(f"Failed to log metrics summary: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
