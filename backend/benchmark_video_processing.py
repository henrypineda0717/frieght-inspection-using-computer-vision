"""
Benchmark script to compare old vs new video processing implementations
"""
import sys
import time
from pathlib import Path
import cv2

sys.path.insert(0, str(Path(__file__).parent))

from app.services.model_manager import ModelManager
from app.services.detection_coordinator import DetectionCoordinator
from app.services.ocr_processor import OCRProcessor
from app.services.damage_classifier import DamageClassifier
from app.services.result_aggregator import ResultAggregator
from app.services.video_processor import VideoProcessor
from app.services.video_processor_realtime import RealtimeVideoProcessor
from app.utils.logger import get_logger

logger = get_logger(__name__)


def benchmark_old_processor(video_path: str, frame_sample_rate: int = 3):
    """Benchmark the old synchronous video processor."""
    print("\n" + "=" * 80)
    print("BENCHMARKING OLD PROCESSOR (Synchronous)")
    print("=" * 80)
    
    # Initialize
    model_manager = ModelManager()
    detection_coordinator = DetectionCoordinator(model_manager)
    ocr_processor = OCRProcessor(model_manager)
    damage_classifier = DamageClassifier()
    result_aggregator = ResultAggregator(ocr_processor, damage_classifier)
    
    processor = VideoProcessor(
        detection_coordinator,
        result_aggregator,
        frame_sample_rate=frame_sample_rate
    )
    
    # Process
    start_time = time.time()
    frame_count = 0
    detection_count = 0
    
    try:
        for annotated_frame, detections, frame_number in processor.process_video(video_path):
            frame_count += 1
            detection_count += len(detections)
    except Exception as e:
        print(f"ERROR: {e}")
        return None
    
    elapsed = time.time() - start_time
    avg_fps = frame_count / elapsed if elapsed > 0 else 0
    
    results = {
        'name': 'Old Processor (Synchronous)',
        'frames': frame_count,
        'detections': detection_count,
        'time': elapsed,
        'fps': avg_fps
    }
    
    print(f"Frames: {frame_count}")
    print(f"Detections: {detection_count}")
    print(f"Time: {elapsed:.2f}s")
    print(f"FPS: {avg_fps:.1f}")
    
    return results


def benchmark_new_processor(video_path: str, detection_interval: int = 3):
    """Benchmark the new threaded video processor."""
    print("\n" + "=" * 80)
    print("BENCHMARKING NEW PROCESSOR (Threaded + Tracking)")
    print("=" * 80)
    
    # Initialize
    model_manager = ModelManager()
    detection_coordinator = DetectionCoordinator(model_manager, use_fp16=True)
    ocr_processor = OCRProcessor(model_manager)
    damage_classifier = DamageClassifier()
    result_aggregator = ResultAggregator(ocr_processor, damage_classifier)
    
    processor = RealtimeVideoProcessor(
        detection_coordinator,
        result_aggregator,
        detection_interval=detection_interval,
        use_fp16=True
    )
    
    # Process
    start_time = time.time()
    frame_count = 0
    detection_count = 0
    
    try:
        for annotated_frame, detections, frame_number in processor.process_video(video_path):
            frame_count += 1
            detection_count += len(detections)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    elapsed = time.time() - start_time
    avg_fps = frame_count / elapsed if elapsed > 0 else 0
    
    results = {
        'name': 'New Processor (Threaded)',
        'frames': frame_count,
        'detections': detection_count,
        'time': elapsed,
        'fps': avg_fps
    }
    
    print(f"Frames: {frame_count}")
    print(f"Detections: {detection_count}")
    print(f"Time: {elapsed:.2f}s")
    print(f"FPS: {avg_fps:.1f}")
    
    return results


def print_comparison(old_results, new_results, video_fps):
    """Print comparison table."""
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)
    
    if not old_results or not new_results:
        print("ERROR: One or both benchmarks failed")
        return
    
    print(f"\n{'Metric':<30} {'Old':<20} {'New':<20} {'Improvement':<15}")
    print("-" * 85)
    
    # Frames
    print(f"{'Frames Processed':<30} {old_results['frames']:<20} {new_results['frames']:<20} {'-':<15}")
    
    # Time
    time_improvement = ((old_results['time'] - new_results['time']) / old_results['time']) * 100
    print(
        f"{'Processing Time (s)':<30} "
        f"{old_results['time']:<20.2f} "
        f"{new_results['time']:<20.2f} "
        f"{time_improvement:>+.1f}%"
    )
    
    # FPS
    fps_improvement = ((new_results['fps'] - old_results['fps']) / old_results['fps']) * 100
    print(
        f"{'Average FPS':<30} "
        f"{old_results['fps']:<20.1f} "
        f"{new_results['fps']:<20.1f} "
        f"{fps_improvement:>+.1f}%"
    )
    
    # Realtime speedup
    old_speedup = old_results['fps'] / video_fps if video_fps > 0 else 0
    new_speedup = new_results['fps'] / video_fps if video_fps > 0 else 0
    print(
        f"{'Realtime Speedup':<30} "
        f"{old_speedup:<20.2f}x "
        f"{new_speedup:<20.2f}x "
        f"{((new_speedup - old_speedup) / old_speedup * 100):>+.1f}%"
    )
    
    # Detections
    print(
        f"{'Total Detections':<30} "
        f"{old_results['detections']:<20} "
        f"{new_results['detections']:<20} "
        f"{'-':<15}"
    )
    
    print("-" * 85)
    
    # Summary
    print("\nSUMMARY:")
    if new_results['fps'] >= 25:
        print("✓ New processor achieves 25+ FPS target")
    else:
        print(f"⚠ New processor FPS: {new_results['fps']:.1f} (target: 25+)")
    
    if fps_improvement > 0:
        print(f"✓ FPS improved by {fps_improvement:.1f}%")
    else:
        print(f"⚠ FPS decreased by {abs(fps_improvement):.1f}%")
    
    if time_improvement > 0:
        print(f"✓ Processing time reduced by {time_improvement:.1f}%")
    else:
        print(f"⚠ Processing time increased by {abs(time_improvement):.1f}%")
    
    print("=" * 80)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Benchmark old vs new video processing"
    )
    parser.add_argument(
        "video",
        help="Path to input video file"
    )
    parser.add_argument(
        "--detection-interval",
        type=int,
        default=3,
        help="Detection interval (default: 3)"
    )
    
    args = parser.parse_args()
    
    # Check video exists
    if not Path(args.video).exists():
        print(f"ERROR: Video not found: {args.video}")
        sys.exit(1)
    
    # Get video info
    cap = cv2.VideoCapture(args.video)
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    print("=" * 80)
    print("VIDEO PROCESSING BENCHMARK")
    print("=" * 80)
    print(f"Video: {args.video}")
    print(f"FPS: {video_fps:.2f}")
    print(f"Total frames: {total_frames}")
    print(f"Detection interval: {args.detection_interval}")
    
    # Run benchmarks
    old_results = benchmark_old_processor(args.video, args.detection_interval)
    new_results = benchmark_new_processor(args.video, args.detection_interval)
    
    # Print comparison
    print_comparison(old_results, new_results, video_fps)


if __name__ == "__main__":
    main()
