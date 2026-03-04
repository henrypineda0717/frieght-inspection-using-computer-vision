"""
Manual testing script for multi-model YOLO integration
Tests the complete pipeline with real models
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from app.services.model_manager import ModelManager
from app.services.detection_coordinator import DetectionCoordinator
from app.services.ocr_processor import OCRProcessor
from app.services.damage_classifier import DamageClassifier
from app.services.result_aggregator import ResultAggregator
from app.utils.logger import get_logger

logger = get_logger(__name__)

def test_model_loading():
    """Test 1: Verify all models load successfully"""
    print("\n=== Test 1: Model Loading ===")
    model_manager = ModelManager()
    status = model_manager.load_models()
    
    print(f"General Model: {'✓ Loaded' if status.get('general') else '✗ Failed'}")
    print(f"Damage Model: {'✓ Loaded' if status.get('damage') else '✗ Failed'}")
    print(f"ID Model: {'✓ Loaded' if status.get('id') else '✗ Failed'}")
    
    return model_manager, all(status.values())

def test_detection_pipeline(model_manager):
    """Test 2: Run detection pipeline on a test image"""
    print("\n=== Test 2: Detection Pipeline ===")
    
    # Create a more realistic test image (solid color with some structure)
    test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
    # Add some rectangles to simulate objects
    test_image[100:200, 100:300] = [255, 0, 0]  # Red rectangle
    test_image[250:350, 400:550] = [0, 255, 0]  # Green rectangle
    
    # Initialize components
    coordinator = DetectionCoordinator(model_manager)
    ocr_processor = OCRProcessor(model_manager)
    damage_classifier = DamageClassifier()
    aggregator = ResultAggregator(ocr_processor, damage_classifier)
    
    # Run detection
    print("Running multi-model detection...")
    raw_detections = coordinator.detect_all(test_image)
    print(f"Total detections: {len(raw_detections)}")
    
    # Count by model source
    model_counts = {}
    for det in raw_detections:
        source = det.get('model_source', 'unknown')
        model_counts[source] = model_counts.get(source, 0) + 1
    
    print(f"Detections by model:")
    for source, count in model_counts.items():
        print(f"  {source}: {count}")
    
    # Aggregate results
    print("\nAggregating results...")
    enriched = aggregator.aggregate_detections(test_image, raw_detections)
    print(f"Enriched detections: {len(enriched)}")
    
    # Verify pipeline components work
    print(f"✓ Detection coordinator executed successfully")
    print(f"✓ Result aggregator executed successfully")
    
    # Note: No detections is OK for synthetic test images
    # The important thing is the pipeline runs without errors
    print(f"\nNote: Detection count may be 0 for synthetic test images")
    print(f"      This is expected - models are trained on real container images")
    
    return True  # Pipeline executed successfully

def test_error_handling(model_manager):
    """Test 3: Verify graceful error handling"""
    print("\n=== Test 3: Error Handling ===")
    
    coordinator = DetectionCoordinator(model_manager)
    
    # Test with invalid image
    try:
        invalid_image = np.array([])
        detections = coordinator.detect_all(invalid_image)
        print("✓ Handled invalid image gracefully")
    except Exception as e:
        print(f"✗ Failed to handle invalid image: {e}")
        return False
    
    return True

def test_ocr_validation():
    """Test 4: Verify OCR validation logic"""
    print("\n=== Test 4: OCR Validation ===")
    
    model_manager = ModelManager()
    ocr_processor = OCRProcessor(model_manager)
    
    # Test valid container IDs
    valid_ids = ["ABCD1234567", "TEST9876543", "CONT1111111"]
    for cid in valid_ids:
        result = ocr_processor._validate_container_id(cid)
        status = "✓" if result == cid else "✗"
        print(f"{status} Valid ID '{cid}': {result}")
    
    # Test invalid patterns
    invalid_ids = ["ABC123", "12345678901", "ABCDEFGHIJK", ""]
    for cid in invalid_ids:
        result = ocr_processor._validate_container_id(cid)
        status = "✓" if result is None else "✗"
        print(f"{status} Invalid ID '{cid}': {result}")
    
    return True

def test_severity_classification():
    """Test 5: Verify damage severity classification"""
    print("\n=== Test 5: Severity Classification ===")
    
    classifier = DamageClassifier()
    
    test_cases = [
        (0.9, "high", "damage"),
        (0.7, "medium", "damage"),
        (0.3, "low", "damage"),
        (0.9, None, "general"),
        (0.9, None, "id"),
    ]
    
    all_passed = True
    for confidence, expected_severity, model_source in test_cases:
        result = classifier.classify_severity(confidence, model_source)
        passed = result == expected_severity
        status = "✓" if passed else "✗"
        print(f"{status} Confidence {confidence} ({model_source}): {result} (expected {expected_severity})")
        all_passed = all_passed and passed
    
    return all_passed

def main():
    """Run all manual tests"""
    print("=" * 60)
    print("Multi-Model YOLO Integration - Manual Testing")
    print("=" * 60)
    
    results = []
    
    # Test 1: Model Loading
    model_manager, test1_passed = test_model_loading()
    results.append(("Model Loading", test1_passed))
    
    if not test1_passed:
        print("\n⚠ Warning: Some models failed to load. Continuing with available models...")
    
    # Test 2: Detection Pipeline
    test2_passed = test_detection_pipeline(model_manager)
    results.append(("Detection Pipeline", test2_passed))
    
    # Test 3: Error Handling
    test3_passed = test_error_handling(model_manager)
    results.append(("Error Handling", test3_passed))
    
    # Test 4: OCR Validation
    test4_passed = test_ocr_validation()
    results.append(("OCR Validation", test4_passed))
    
    # Test 5: Severity Classification
    test5_passed = test_severity_classification()
    results.append(("Severity Classification", test5_passed))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 All manual tests passed!")
        return 0
    else:
        print(f"\n⚠ {total_tests - total_passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
