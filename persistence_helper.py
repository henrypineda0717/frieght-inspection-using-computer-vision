"""
Compatibility wrapper for old app.py
Redirects to new backend structure
"""
import asyncio

def persist_analysis_result(db, image_data, analysis_result, inspection_stage=None):
    """Wrapper for old persist function"""
    # Lazy import to avoid circular dependency
    from backend.app.services.persistence_service import PersistenceService
    
    service = PersistenceService(db)
    # Run async function synchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            service.persist_analysis(image_data, analysis_result, inspection_stage)
        )
    finally:
        loop.close()

def persist_video_analysis(db, video_results, container_id="UNKNOWN", inspection_stage=None):
    """Wrapper for old persist video function"""
    # Lazy import to avoid circular dependency
    from backend.app.services.persistence_service import PersistenceService
    
    service = PersistenceService(db)
    # Run async function synchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            service.persist_video_analysis(video_results, inspection_stage)
        )
    finally:
        loop.close()

__all__ = ["persist_analysis_result", "persist_video_analysis"]
