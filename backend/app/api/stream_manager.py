import asyncio
import logging
import multiprocessing
import os
import re
import shutil
from typing import Optional

from .config import HLS_BASE_DIR, DISPLAY_WIDTH, DISPLAY_HEIGHT
from .run_camera import run_camera_pipeline

logger = logging.getLogger(__name__)


class SingleCameraManager:
    """Manages a single camera pipeline backed by GStreamer."""

    def __init__(self):
        self.display_width = DISPLAY_WIDTH
        self.display_height = DISPLAY_HEIGHT
        self.cam_id: Optional[str] = None
        self.camera_config: Optional[dict] = None
        self.camera_process_info = None
        self.shutdown_event = multiprocessing.Event()
        self._initialized = False
        self._lock = asyncio.Lock()
        self.gpu_available = True

    async def start(self, config: Optional[dict] = None) -> bool:
        async with self._lock:
            if config:
                await self._configure_camera(config)

            if not self.camera_config or not self.cam_id:
                logger.error("Camera start attempted without configuration")
                return False

            if self.camera_process_info is not None:
                logger.warning("Camera process already running")
                return True

            await self._prepare_camera_hls_directory()

            try:
                parent_conn, child_conn = multiprocessing.Pipe()
                process_args = {
                    'cam_id': self.cam_id,
                    'config': self.camera_config,
                    'gpu_available': self.gpu_available,
                    'display_width': self.display_width,
                    'display_height': self.display_height,
                    'ai_in_q': None,
                    'ai_out_q': None,
                    'shutdown_pipe': child_conn,
                    'performance_stats': None
                }

                process = multiprocessing.Process(
                    target=run_camera_pipeline,
                    args=(process_args,),
                    name=f"CameraProcess-{self.cam_id}",
                    daemon=True
                )
                process.start()

                self.camera_process_info = {
                    'process': process,
                    'pipe': parent_conn,
                    'config': self.camera_config,
                    'cam_id': self.cam_id
                }

                if parent_conn.poll(30.0):
                    response = parent_conn.recv()
                    if response.get('status') == 'initialized':
                        logger.info(f"Camera {self.cam_id} started successfully")
                        return True
                    logger.error(f"Camera {self.cam_id} failed to initialize: {response}")
                    return False
                logger.warning(f"Timeout waiting for camera {self.cam_id}; assuming it is running")
                return True

            except Exception as exc:
                logger.error(f"Error starting camera: {exc}")
                return False

    async def stop(self) -> None:
        async with self._lock:
            logger.info("Shutting down camera manager")
            if self.camera_process_info:
                await self._stop_camera_process()
            self._initialized = False

    async def _stop_camera_process(self):
        try:
            if not self.camera_process_info:
                return
            proc_info = self.camera_process_info
            pipe = proc_info['pipe']
            if pipe:
                try:
                    pipe.send({'command': 'shutdown'})
                    if pipe.poll(10.0):
                        response = pipe.recv()
                        logger.info(f"Camera {self.cam_id} shutdown response: {response}")
                except (BrokenPipeError, EOFError):
                    pass

            proc_info['process'].join(timeout=5.0)
            if proc_info['process'].is_alive():
                logger.warning(f"Force terminating camera process {self.cam_id}")
                proc_info['process'].terminate()
                proc_info['process'].join(timeout=2.0)
                if proc_info['process'].is_alive():
                    proc_info['process'].kill()

            if pipe:
                pipe.close()
            self.camera_process_info = None
            logger.info(f"Camera {self.cam_id} stopped")
        except Exception as exc:
            logger.error(f"Error stopping camera: {exc}")

    async def _prepare_camera_hls_directory(self) -> None:
        if not self.cam_id:
            return
        try:
            os.makedirs(HLS_BASE_DIR, exist_ok=True)
            camera_dir = os.path.join(HLS_BASE_DIR, self.cam_id)
            if os.path.isdir(camera_dir):
                shutil.rmtree(camera_dir)
            os.makedirs(camera_dir, exist_ok=True)
            logger.info(f"Prepared HLS dir: {camera_dir}")
        except Exception as exc:
            logger.error(f"Failed to prepare HLS dir: {exc}")

    async def _configure_camera(self, config: dict) -> bool:
        self.camera_config = config
        self.cam_id = self._get_safe_cam_id(config)
        self._initialized = True
        await self._prepare_camera_hls_directory()
        logger.info(f"Configured camera stream: {self.cam_id}")
        return True

    @staticmethod
    def _get_safe_cam_id(cfg: dict) -> str:
        source = str(cfg.get("source") or cfg.get("video_path") or cfg.get("name") or "")
        if source.startswith("rtsp://"):
            port_match = re.search(r':(\d+)', source)
            if port_match:
                return f"rtsp{port_match.group(1)}"
            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', source)
            if ip_match:
                return f"rtsp{ip_match.group(1).replace('.', '')}"
            return "rtsp_stream"
        raw_name = str(cfg.get("name") or cfg.get("id", "unknown")).strip()
        safe_name = re.sub(r'[^a-zA-Z0-9]', '', raw_name)
        return safe_name or "camera"

    def get_status(self) -> dict:
        return {
            "cam_id": self.cam_id,
            "running": self.camera_process_info is not None,
            "playlist_url": f"/hls/{self.cam_id}/playlist.m3u8" if self.cam_id else None
        }
