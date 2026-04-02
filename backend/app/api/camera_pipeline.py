import asyncio
import gi
import numpy as np
import time
import os
import logging
import multiprocessing as mp
import queue
from typing import Optional, Dict

from .gstreamer_reader import create_video_reader_pipeline
from .hls_encode import create_hls_pipeline

gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GLib
from multiprocessing.connection import Connection 
from .config import VIDEO_SOURCE, HLS_BASE_DIR

logger = logging.getLogger(__name__)

class CameraPipeline:    
    def __init__(self, 
                 cam_id: str, 
                 config: dict, 
                 gpu_available: bool,
                 display_width: int, 
                 display_height: int,
                 ai_in_q: mp.Queue,    
                 ai_out_q: mp.Queue,   
                 shutdown_pipe: Optional[Connection] = None,
                 performance_stats: Dict = None):
        
        # Core identification and communication
        self.cam_id = cam_id
        self.config = config
        self.gpu_available = gpu_available
        self.ai_in_q = ai_in_q
        self.ai_out_q = ai_out_q
        self.shutdown_pipe = shutdown_pipe
        self.performance_stats = performance_stats

        # Video source resolution logic
        camera_name = str(config.get('name', '')).strip()
        source_override = config.get('source')
        if source_override:
            self.video_source = source_override
        else:
            self.video_source = f"{VIDEO_SOURCE}/{camera_name}.mp4" if camera_name else ''
        self.main_loop_event_loop = asyncio.new_event_loop()
        
        # Frame settings
        self.width = 640
        self.height = 480
        self.fps = 30
        self.duration_ns = int(Gst.SECOND / self.fps)

        # HLS setup
        self.hls_output_dir = os.path.join(f"{HLS_BASE_DIR}/", cam_id)
        os.makedirs(self.hls_output_dir, exist_ok=True)

        # Pipeline state
        self.source_pipeline = None
        self.appsink = None
        self.hls_pipeline = None
        self.appsource = None
        
        self.frame_count = 0
        self.is_running = False
        self.start_time = None
        self.main_loop = None
        self.last_status_update = time.time()
        self.process_shutdown = False

        if not Gst.is_initialized():
            Gst.init(None)
    
    def initialize(self):
        """Initialize GStreamer pipelines."""
        if not self.video_source:
            raise ValueError(f"No video source for {self.cam_id}")

        os.environ["NVBUF_TRANSFORM_SKIP_CONFIG"] = "1"

        self.source_pipeline, self.appsink = create_video_reader_pipeline(
            self.video_source, self.width, self.height
        )

        self.hls_pipeline, self.appsource, _ = create_hls_pipeline(
            self.width, self.height, self.hls_output_dir,
            target_segment_duration=2, max_segments=6
        )
        

        self.appsink.connect("new-sample", self.on_new_sample)
        
        bus = self.hls_pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)

        return True

    def on_new_sample(self, sink):
            if self.process_shutdown:
                return Gst.FlowReturn.EOS

            sample = sink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.OK

            buffer = sample.get_buffer()
            # Keep original timestamps to prevent HLS jitter
            pts, dts = buffer.pts, buffer.dts

            success, mapinfo = buffer.map(Gst.MapFlags.READ)
            if not success:
                return Gst.FlowReturn.ERROR

            try:
                width = self.width
                height = self.height
                format_tag = 'BGRx'
                caps = sample.get_caps()
                if caps and caps.get_size() > 0:
                    structure = caps.get_structure(0)
                    if structure.has_field('width'):
                        width = structure.get_int('width')[1]
                    if structure.has_field('height'):
                        height = structure.get_int('height')[1]
                    if structure.has_field('format'):
                        format_tag = structure.get_string('format') or format_tag

                channels = 4 if 'x' in format_tag.lower() or 'a' in format_tag.lower() else 3
                expected_size = width * height * channels
                actual_size = mapinfo.size
                if actual_size < expected_size:
                    channels = max(1, actual_size // (width * height))
                    expected_size = width * height * channels
                frame_data = mapinfo.data[:expected_size]
                frame_bgrx = np.ndarray((height, width, channels), dtype=np.uint8, buffer=frame_data).copy()
                if channels > 3:
                    frame_bgr = np.ascontiguousarray(frame_bgrx[:, :, :3])
                else:
                    frame_bgr = np.ascontiguousarray(frame_bgrx)

                try:
                    if not self.ai_in_q.full():
                        self.ai_in_q.put_nowait(frame_bgr)
                except: pass

                if self.ai_out_q is not None:
                    try:
                        worker_data = self.ai_out_q.get(timeout=0.2)
                        _, raw_gpu_result = worker_data 

                        if raw_gpu_result is not None:
                            print("Processing AI results for annotation...")
                            annotated_bgr = self.main_loop_event_loop.run_until_complete(
                                # This is a placeholder for the actual annotation logic, which would depend on the structure of raw_gpu_result
                            )
                            print("Annotation complete, updating frame buffer.")
                            frame_bgrx[:, :, :3] = annotated_bgr
                        else:
                            print("Bypassing AI annotation, using original frame.")
                    except queue.Empty:
                        print('AI output queue empty, bypassing annotation.')

                # 4. Create output buffer for HLS
                gst_buffer = Gst.Buffer.new_wrapped(frame_bgrx.tobytes())
                gst_buffer.pts = pts if pts != Gst.CLOCK_TIME_NONE else (self.frame_count * self.duration_ns)
                gst_buffer.dts = dts if dts != Gst.CLOCK_TIME_NONE else gst_buffer.pts
                gst_buffer.duration = self.duration_ns

            finally:
                buffer.unmap(mapinfo)

            # Push to HLS Encoder
            self.appsource.emit("push-buffer", gst_buffer)
            self.frame_count += 1
            return Gst.FlowReturn.OK
        

    def _check_shutdown(self):
        if self.shutdown_pipe and self.shutdown_pipe.poll():
            try:
                message = self.shutdown_pipe.recv()
                if message.get('command') == 'shutdown':
                    self.stop()
                    return False
            except:
                self.process_shutdown = True
                return False
        
        # Update performance metrics
        if self.performance_stats is not None and (time.time() - self.last_status_update > 1.0):
            runtime = time.time() - self.start_time if self.start_time else 0
            self.performance_stats[self.cam_id] = {
                "status": "running" if self.is_running else "stopped",
                "fps": self.frame_count / runtime if runtime > 0 else 0,
                "pid": os.getpid()
            }
            self.last_status_update = time.time()
        return True

    def start(self):
        try:
            if not self.initialize(): return False
            self.start_time = time.time()
            self.is_running = True

            self.hls_pipeline.set_state(Gst.State.PLAYING)
            self.source_pipeline.set_state(Gst.State.PLAYING)

            self.main_loop = GLib.MainLoop()
            GLib.timeout_add(100, self._check_shutdown)
            self.main_loop.run()
            return True
        except Exception as e:
            logger.error(f"[{self.cam_id}] Start failed: {e}")
            self.stop()
            return False

    def stop(self):
        self.is_running = False
        self.process_shutdown = True
        if self.main_loop: self.main_loop.quit()
        if self.source_pipeline: self.source_pipeline.set_state(Gst.State.NULL)
        if self.hls_pipeline: self.hls_pipeline.set_state(Gst.State.NULL)
        
        if self.performance_stats and self.cam_id in self.performance_stats:
            del self.performance_stats[self.cam_id]

    def on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"[{self.cam_id}] GStreamer Error: {err}")
