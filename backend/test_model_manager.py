"""
Quick test script to verify ModelManager functionality (V3: YOLOE + RF-DETR + PaddleOCR)
"""
import sys
import os
from pathlib import Path

# CRITICAL: Prevent PaddleOCR Segmentation Fault before imports
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
os.environ['FLAGS_use_onednn'] = '0'
os.environ['OMP_NUM_THREADS'] = '1'

# Add backend to path
backend_path = Path(__file__).resolve().parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.model_manager import ModelManager
from app.utils.logger import setup_logging
from app.config import settings

# Setup logging
setup_logging(level="INFO")

def test_model_manager():
    """Test ModelManager initialization and model loading"""
    print("\n" + "="*60)
    print("DIAGNOSTIC: Path Check")
    print(f"Current Working Dir: {os.getcwd()}")
    print(f"Settings ROOT_DIR:   {settings.ROOT_DIR}")
    print(f"Settings MODELS_DIR: {settings.MODELS_DIR}")
    
    # Check if files exist physically
    yoloe_file = settings.MODELS_DIR / settings.YOLOE_MODEL_PATH
    rtdetr_file = settings.MODELS_DIR / settings.RT_DETR_MODEL_PATH
    print(f"Looking for YOLOE at:   {yoloe_file} [{'EXISTS' if yoloe_file.exists() else 'MISSING'}]")
    print(f"Looking for RF-DETR at: {rtdetr_file} [{'EXISTS' if rtdetr_file.exists() else 'MISSING'}]")
    print("="*60 + "\n")

    # Test 1: Singleton pattern
    print("Test 1: Singleton pattern")
    manager1 = ModelManager()
    manager2 = ModelManager()
    assert manager1 is manager2, "ModelManager should be a singleton"
    print("✅ Singleton pattern works correctly\n")
    
    # Test 2: Load models
    print("Test 2: Load models (YOLOE & RF-DETR)")
    # Note: load_models returns a dict of the models we actually attempted to load
    status = manager1.load_models(warmup=True)
    print(f"Load status: {status}")
    
    loaded_count = sum(status.values())
    print(f"✅ Loaded {loaded_count} model(s)\n")
    
    # Test 3: Check model availability (Updated for new model names)
    print("Test 3: Check model availability")
    for model_type in ['General', 'Damage']:
        available = manager1.is_model_available(model_type)
        status_str = "✅ Available" if available else "❌ Not available"
        print(f"  {model_type.upper()} model: {status_str}")
    print()
    
    # Test 4: Check invalid model type
    print("Test 4: Check invalid model type")
    invalid_available = manager1.is_model_available('invalid_model_name')
    assert not invalid_available, "Invalid model type should return False"
    print("✅ Invalid model type handled correctly\n")
    
    # Test 5: Lazy OCR loading (PaddleOCR)
    print("Test 5: Lazy OCR loading (PaddleOCR)")
    try:
        ocr = manager1.get_ocr_engine()
        if ocr:
            print("✅ OCR engine loaded successfully")
            
            # # Verify caching
            # ocr_engine2 = manager1.get_ocr_engine()
            # assert ocr_engine is ocr_engine2, "OCR engine should be cached"
            # print("✅ OCR engine caching works correctly\n")
        else:
            print("❌ OCR engine returned None (Check logs for initialization errors)\n")
    except Exception as e:
        print(f"⚠️  OCR engine loading failed: {e}\n")
    
    print("="*60)
    print("All tests completed!")
    print("="*60)

if __name__ == "__main__":
    test_model_manager()