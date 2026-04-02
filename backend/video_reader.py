import cv2
import time
import threading
from collections import deque
import logging

logger = logging.getLogger(__name__)

def video_reader(cam_id: str, video_path: str, yolo_queue: deque, shutdown_event: threading.Event,
                 display_width: int, display_height: int, target_fps: int, frame_skip_threshold: int, frame_skip_var):
    frame_interval = 1 / target_fps
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Failed to open video: {video_path}")
        return

    frame_skip_counter = 0
    total_dropped_frames = 0
    frame_count = 0
    
    print(f"Video reader started for {cam_id} at {target_fps} FPS")

    while not shutdown_event.is_set():
        start_time = time.time()

        if len(yolo_queue) > frame_skip_threshold:
            frame_skip_counter = (frame_skip_counter + 1) % 2
            if frame_skip_counter != 0:
                cap.grab()
                total_dropped_frames += 1
                elapsed = time.time() - start_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                continue

        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame_count += 1
        skip_val = frame_skip_var.get()
        if skip_val > 0 and (frame_count % (skip_val + 1)) != 1:
            continue

        display_frame = cv2.resize(frame, (display_width, display_height))
        if len(yolo_queue) < yolo_queue.maxlen:
            yolo_queue.append(display_frame)
        else:
            total_dropped_frames += 1

        elapsed = time.time() - start_time
        if elapsed < frame_interval:
            time.sleep(frame_interval - elapsed)

    cap.release()
    print(f"Video reader stopped for {cam_id}")
