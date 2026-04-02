import os
import asyncio
import multiprocessing
import re
import logging
import httpx
import requests
from typing import Optional

from api.config import HLS_BASE_DIR, BACKEND_URL, DISPLAY_WIDTH, DISPLAY_HEIGHT
from api.run_camera import run_camera_pipeline

logger = logging.getLogger(__name__)


class SingleCameraManager:
    """
    Manages a single camera pipeline (no AI batch worker).
    """

    def __init__(self):
        self.display_width = DISPLAY_WIDTH
        self.display_height = DISPLAY_HEIGHT
        self.cam_id = None
        self.camera_config = None
        self.camera_process_info = None  # Will hold process and pipe

        self.shutdown_event = multiprocessing.Event()
        self._initialized = False

        self.gpu_available = True  # Still used by camera pipeline for encoding

        self.backend_url = BACKEND_URL

    async def async_init(self):
        """Load camera configuration and prepare the HLS directory."""
        if not await self._wait_for_backend():
            return False

        await self._clear_hls_directory()

        if not await self._load_camera_config():
            logger.error("No camera configuration loaded")
            return False

        # Create HLS directory for the camera
        hls_dir = os.path.join(HLS_BASE_DIR, self.cam_id)
        os.makedirs(hls_dir, exist_ok=True)
        logger.info(f"Created HLS dir: {hls_dir}")

        self._initialized = True
        return True

    async def start(self):
        """Start the camera process."""
        if not self._initialized:
            if not await self.async_init():
                return False

        if self.camera_process_info is not None:
            logger.warning("Camera process already running")
            return True

        try:
            parent_conn, child_conn = multiprocessing.Pipe()

            process_args = {
                'cam_id': self.cam_id,
                'config': self.camera_config,
                'gpu_available': self.gpu_available,
                'display_width': self.display_width,
                'display_height': self.display_height,
                'ai_in_q': None,        # No AI worker
                'ai_out_q': None,       # No AI worker
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

            if parent_conn.poll(5.0):
                response = parent_conn.recv()
                if response.get('status') == 'initialized':
                    logger.info(f"Camera {self.cam_id} started successfully")
                    return True
                else:
                    logger.error(f"Camera {self.cam_id} failed to initialize: {response}")
                    return False
            else:
                logger.error(f"Timeout waiting for camera {self.cam_id}")
                return False

        except Exception as e:
            logger.error(f"Error starting camera: {e}")
            return False

    async def stop(self):
        """Stop the camera process."""
        logger.info("Shutting down camera manager")
        if self.camera_process_info:
            await self._stop_camera_process()
        self._initialized = False

    async def _stop_camera_process(self):
        """Gracefully stop the camera process."""
        try:
            if not self.camera_process_info:
                return

            proc_info = self.camera_process_info
            pipe = proc_info['pipe']

            # Send shutdown signal
            if pipe:
                try:
                    pipe.send({'command': 'shutdown'})
                    # Wait for ack (optional)
                    if pipe.poll(10.0):
                        response = pipe.recv()
                        logger.info(f"Camera {self.cam_id} shutdown response: {response}")
                except (BrokenPipeError, EOFError):
                    pass

            # Wait for process to finish
            proc_info['process'].join(timeout=5.0)

            # Force terminate if still alive
            if proc_info['process'].is_alive():
                logger.warning(f"Force terminating camera process {self.cam_id}")
                proc_info['process'].terminate()
                proc_info['process'].join(timeout=2.0)
                if proc_info['process'].is_alive():
                    proc_info['process'].kill()

            # Clean up
            if pipe:
                pipe.close()

            self.camera_process_info = None
            logger.info(f"Camera {self.cam_id} stopped")

        except Exception as e:
            logger.error(f"Error stopping camera: {e}")

    async def _wait_for_backend(self):
        """Wait for backend API to be ready."""
        for attempt in range(10):
            try:
                response = requests.get(self.backend_url, timeout=5)
                if response.status_code == 200:
                    logger.info("Backend ready")
                    return True
            except Exception:
                logger.info(f"Waiting for backend... {attempt + 1}/10")
                await asyncio.sleep(2)
        logger.error("Backend not ready")
        return False

    async def _clear_hls_directory(self):
        """Clear the HLS output directory for the camera."""
        try:
            if os.path.exists(HLS_BASE_DIR):
                for item in os.listdir(HLS_BASE_DIR):
                    item_path = os.path.join(HLS_BASE_DIR, item)
                    if os.path.isdir(item_path):
                        import shutil
                        shutil.rmtree(item_path)
            os.makedirs(HLS_BASE_DIR, exist_ok=True)
            logger.info("HLS directory cleared")
        except Exception as e:
            logger.error(f"Clear HLS error: {e}")

    async def _load_camera_config(self):
        """
        Load the first camera configuration from the backend.
        (If you need a specific camera, pass an ID or name.)
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.backend_url}/api/camera-config")
                configs = response.json()
        except Exception as e:
            logger.error(f"Load configs error: {e}")
            return False

        if not configs:
            logger.warning("No camera configurations found")
            return False

        # Take the first configuration
        cfg = configs[0]
        self.cam_id = self._get_safe_cam_id(cfg)
        self.camera_config = cfg
        logger.info(f"Loaded camera: {self.cam_id}")
        return True

    @staticmethod
    def _get_safe_cam_id(cfg: dict) -> str:
        """
        Generate a safe ID from the camera source.
        (Same logic as the original code.)
        """
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