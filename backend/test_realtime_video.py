"""
Test script for real-time video processing optimization
"""

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.model_manager import ModelManager
from app.services.detection_coordinator import DetectionCoordinator
from app.services.ocr_processor import OCRProcessor
from app.services.damage_classifier import DamageClassifier
from app.services.result_aggregator import ResultAggregator
from app.services.video_processor_realtime import RealtimeVideoProcessor
from app.utils.logger import get_logger
import cv2

logger = get_logger(__name__)


def test_realtime_processing(video_path: str, output_path: str = None):
    """
    Test real-time video processing with performance metrics.
    
    Args:
        video_path: Path to input video
        output_path: Optional path for output video
    """
    
    print("=" * 80)
    print("REAL-TIME VIDEO PROCESSING TEST")
    print("=" * 80)
    
    # Initialize components
    print("\n[1/5] Initializing models...")
    model_manager = ModelManager()
    load_status = model_manager.load_models(warmup=True)
    
    for m, success in load_status.items():
        print(f"  - {m}: {'LOADED' if success else 'FAILED'}")
    detection_coordinator = DetectionCoordinator(model_manager, use_fp16=True)
    ocr_processor = OCRProcessor(model_manager)
    damage_classifier = DamageClassifier()
    result_aggregator = ResultAggregator(ocr_processor, damage_classifier)
    
    # Initialize real-time processor
    print("[2/5] Initializing real-time processor...")
    processor = RealtimeVideoProcessor(
        detection_coordinator,
        result_aggregator,
        detection_interval=3,  # Detect every 3 frames
        max_queue_size=30,
        use_fp16=False
    )
    
    # Get video info
    print(f"[3/5] Opening video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Cannot open video: {video_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    cap.release()
    
    print(f"  - Resolution: {width}x{height}")
    print(f"  - FPS: {fps:.2f}")
    print(f"  - Total frames: {total_frames}")
    print(f"  - Duration: {duration:.2f}s")
    
    # Setup output writer if needed
    out = None
    if output_path:
        print(f"[4/5] Creating output video: {output_path}")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    else:
        print("[4/5] Skipping output video (no output path specified)")
    
    # Process video
    print("[5/5] Processing video with real-time pipeline...")
    print("-" * 80)
    
    start_time = time.time()
    frame_count = 0
    detection_count = 0
    
    try:
        # Process only the very first frame
        for annotated_frame, detections, frame_number in processor.process_video(video_path):
            frame_count += 1
            detection_count += len(detections)
            
            cv2.imwrite("first_frame_output.jpg", annotated_frame)
                        
            annotated_frame = cv2.resize(annotated_frame, (1280, 1080))
            
            cv2.imshow('window_name', annotated_frame)
    
            # Press 'q' to quit early
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            # print(f"Detections found: {len(detections)}")
            
            # for d in detections:
            #     print(f"- {d['class_name']} ({d['confidence']:.2f})")
            
            # # This stops the loop immediately after the first frame
            # print("Processing finished after 1 frame.")
            
            # # Progress update every 30 frames
            # if frame_count % 30 == 0:
            #     elapsed = time.time() - start_time
            #     current_fps = frame_count / elapsed if elapsed > 0 else 0
            #     progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
            #     print(
            #         f"  Frame {frame_count}/{total_frames} ({progress:.1f}%) | "
            #         f"FPS: {current_fps:.1f} | "
            #         f"Detections: {len(detections)}"
            #     )
    
        cv2.destroyAllWindows()
        
    except KeyboardInterrupt:
        print("\n\nProcessing interrupted by user")
    
    except Exception as e:
        print(f"\n\nERROR during processing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if out:
            out.release()
        
        # Final statistics
        elapsed = time.time() - start_time
        avg_fps = frame_count / elapsed if elapsed > 0 else 0
        
        print("-" * 80)
        print("\nPROCESSING COMPLETE")
        print("=" * 80)
        print(f"Frames processed: {frame_count}/{total_frames}")
        print(f"Total detections: {detection_count}")
        print(f"Processing time: {elapsed:.2f}s")
        print(f"Average FPS: {avg_fps:.1f}")
        print(f"Speedup: {avg_fps/fps:.2f}x realtime" if fps > 0 else "")
        
        if avg_fps >= 25:
            print("\n✓ SUCCESS: Achieved 25+ FPS target!")
        else:
            print(f"\n⚠ WARNING: FPS below target (got {avg_fps:.1f}, need 25+)")
            print("  Suggestions:")
            print("  - Increase detection_interval (e.g., 3 → 5)")
            print("  - Enable GPU with CUDA")
            print("  - Reduce video resolution")
        
        if output_path:
            print(f"\nOutput saved to: {output_path}")
        
        print("=" * 80)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test real-time video processing optimization"
    )
    parser.add_argument(
        "video",
        help="Path to input video file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to output video file (optional)",
        default=None
    )
    
    args = parser.parse_args()
    
    # Check if input exists
    if not Path(args.video).exists():
        print(f"ERROR: Video file not found: {args.video}")
        sys.exit(1)
    
    # Run test
    test_realtime_processing(args.video, args.output)


if __name__ == "__main__":
    main()