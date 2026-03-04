"""
Test OCR processor with a simple test image
"""
import numpy as np
import cv2
from app.services.model_manager import ModelManager
from app.services.ocr_processor import OCRProcessor
from app.utils.logger import setup_logging

# Setup logging to see debug output
setup_logging(level="INFO")

# Initialize components
model_manager = ModelManager()
ocr_processor = OCRProcessor(model_manager)

# Create a simple test image with text
print("=" * 60)
print("Testing OCR Processor")
print("=" * 60)

# Test 1: Check regex pattern
print("\n1. Testing regex pattern:")
test_ids = [
    "MSCU1234567",  # Valid
    "TEMU9876543",  # Valid
    "ABCJ1234567",  # Valid
    "ABCD1234567",  # Invalid (4 letters)
    "MSC1234567",   # Invalid (only 2 letters)
]

for test_id in test_ids:
    match = ocr_processor.container_id_pattern.search(test_id)
    print(f"   {test_id}: {'✅ MATCH' if match else '❌ NO MATCH'}")

# Test 2: Check character values
print("\n2. Testing character value mapping:")
print(f"   A = {ocr_processor.char_values['A']} (expected: 10)")
print(f"   B = {ocr_processor.char_values['B']} (expected: 12)")
print(f"   Z = {ocr_processor.char_values['Z']} (expected: 36)")
print(f"   11 in values? {11 in ocr_processor.char_values.values()} (expected: False)")

# Test 3: Check validation
print("\n3. Testing validation:")
test_texts = [
    "MSCU1234567",
    "Container: MSCU1234567 Status: OK",
    "ABCD1234567",
    "Invalid text",
]

for text in test_texts:
    result = ocr_processor._validate_container_id(text)
    print(f"   '{text}' -> {result}")

# Test 4: Test with actual OCR (if you have a test image)
print("\n4. Testing with OCR engine:")
try:
    # Create a blank image
    test_image = np.ones((200, 400, 3), dtype=np.uint8) * 255
    
    # Add some text using OpenCV (this won't be perfect but tests the pipeline)
    cv2.putText(test_image, "MSCU1234567", (50, 100), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
    
    # Try to extract
    bbox = (0, 0, 400, 200)
    result = ocr_processor.extract_container_id(test_image, bbox)
    print(f"   OCR result: {result}")
    
except Exception as e:
    print(f"   ❌ OCR test failed: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
