# app/services/session_manager.py
import threading
import uuid
import logging
from typing import Dict, Optional
from app.services.video_processor_realtime import RealtimeVideoProcessor

logger = logging.getLogger(__name__)

class VideoSession:
    def __init__(self, processor: RealtimeVideoProcessor, video_path: str):
        self.session_id = str(uuid.uuid4())
        self.processor = processor
        self.video_path = video_path
        self.command_queue = processor.command_queue
        self.active = True
        self.lock = threading.Lock()

    def get_latest_detections(self):
        return self.processor.get_current_detections()

class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, VideoSession] = {}
        self._lock = threading.Lock()
        logger.debug(f"SessionManager instance created, id={id(self)}")

    def create_session(self, processor: RealtimeVideoProcessor, video_path: str) -> str:
        session = VideoSession(processor, video_path)
        with self._lock:
            self._sessions[session.session_id] = session
        logger.debug(f"Session created: {session.session_id}, total sessions: {list(self._sessions.keys())}")
        return session.session_id

    def get_session(self, session_id: str) -> Optional[VideoSession]:
        with self._lock:
            session = self._sessions.get(session_id)
        logger.debug(f"get_session({session_id}) -> {'found' if session else 'not found'}, current keys: {list(self._sessions.keys())}")
        return session

    def remove_session(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                # Signal processor to stop
                self._sessions[session_id].processor.stop_event.set()
                del self._sessions[session_id]
                logger.debug(f"Session removed: {session_id}, remaining: {list(self._sessions.keys())}")
            else:
                logger.debug(f"Attempted to remove non-existent session: {session_id}")

session_manager = SessionManager()