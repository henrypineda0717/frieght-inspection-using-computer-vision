"""
Quick Optimization Script - Apply immediate performance improvements
Run this script to apply Phase 1 optimizations automatically
"""
import os
import sys
from pathlib import Path

def create_optimized_env():
    """Create optimized .env file"""
    env_content = """# Container Inspection System - Optimized Configuration

# Application
DEBUG=false
APP_NAME=Container Inspection System
APP_VERSION=2.0.0

# Server
HOST=0.0.0.0
PORT=8000

# Database (SQLite for development, PostgreSQL for production)
DATABASE_URL=sqlite:///./inspections.db
# DATABASE_URL=postgresql://user:pass@localhost:5432/inspections

# GPU Acceleration (CRITICAL for performance)
USE_FP16=true
CUDA_VISIBLE_DEVICES=0

# Model Optimization
YOLOV10_IMGSZ=480
DEFAULT_IMGSZ=640
MODEL_WARMUP=true

# Model Confidence Thresholds
GENERAL_MODEL_CONFIDENCE=0.5
DAMAGE_MODEL_CONFIDENCE=0.5
ID_MODEL_CONFIDENCE=0.5

# Quick Mode (context-aware optimization)
QUICK_MODE=false

# OCR Settings
OCR_GPU=false  # Set to true if you have CUDA GPU

# Video Processing
FRAME_SAMPLE_RATE=3
VIDEO_BATCH_SIZE=100

# Detection Cache (NEW - improves performance)
ENABLE_DETECTION_CACHE=true
DETECTION_CACHE_SIZE=1000

# CORS
CORS_ORIGINS=*
"""
    
    env_path = Path("backend/.env")
    
    if env_path.exists():
        print(f"⚠️  {env_path} already exists")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Skipping .env creation")
            return False
    
    env_path.write_text(env_content)
    print(f"✓ Created optimized {env_path}")
    return True


def clear_python_cache():
    """Clear Python bytecode cache"""
    import subprocess
    
    print("\n🧹 Clearing Python cache...")
    
    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("❌ backend/ directory not found")
        return False
    
    # Use the existing clear_cache.py script
    clear_script = backend_dir / "clear_cache.py"
    if clear_script.exists():
        try:
            subprocess.run([sys.executable, str(clear_script)], check=True)
            print("✓ Cache cleared successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to clear cache: {e}")
            return False
    else:
        print("⚠️  clear_cache.py not found, clearing manually...")
        
        # Manual cache clearing
        import shutil
        count = 0
        for pycache in backend_dir.rglob("__pycache__"):
            shutil.rmtree(pycache, ignore_errors=True)
            count += 1
        
        for pyc in backend_dir.rglob("*.pyc"):
            pyc.unlink(missing_ok=True)
            count += 1
        
        print(f"✓ Cleared {count} cache files/directories")
        return True


def check_dependencies():
    """Check if required dependencies are installed"""
    print("\n📦 Checking dependencies...")
    
    required = {
        'torch': 'PyTorch',
        'ultralytics': 'YOLO',
        'paddleocr': 'PaddleOCR',
        'boxmot': 'ByteTrack',
        'fastapi': 'FastAPI'
    }
    
    missing = []
    for package, name in required.items():
        try:
            __import__(package)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ❌ {name} (missing)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True


def check_gpu():
    """Check GPU availability"""
    print("\n🎮 Checking GPU...")
    
    try:
        import torch
        
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            print(f"  ✓ CUDA available: {device_name}")
            print(f"  ✓ CUDA version: {torch.version.cuda}")
            return True
        else:
            print("  ⚠️  CUDA not available (CPU mode)")
            print("  💡 Performance will be limited without GPU")
            return False
    except ImportError:
        print("  ❌ PyTorch not installed")
        return False


def run_tests():
    """Run basic tests"""
    print("\n🧪 Running tests...")
    
    import subprocess
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "backend/tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("  ✓ All tests passed")
            return True
        else:
            print("  ⚠️  Some tests failed")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return False
    except subprocess.TimeoutExpired:
        print("  ⚠️  Tests timed out")
        return False
    except Exception as e:
        print(f"  ❌ Failed to run tests: {e}")
        return False


def print_summary(results):
    """Print optimization summary"""
    print("\n" + "="*60)
    print("OPTIMIZATION SUMMARY")
    print("="*60)
    
    for task, success in results.items():
        status = "✓" if success else "❌"
        print(f"{status} {task}")
    
    print("\n" + "="*60)
    
    if all(results.values()):
        print("🎉 All optimizations applied successfully!")
        print("\nNext steps:")
        print("1. Restart your server: uvicorn app.main:app --reload")
        print("2. Test with: curl -X POST http://localhost:8000/api/analysis/ -F 'image=@test.jpg'")
        print("3. Monitor performance in logs")
    else:
        print("⚠️  Some optimizations failed. Check errors above.")
        print("\nYou can still proceed, but performance may not be optimal.")


def main():
    """Main optimization script"""
    print("="*60)
    print("QUICK OPTIMIZATION SCRIPT")
    print("="*60)
    print("\nThis script will apply Phase 1 optimizations:")
    print("1. Create optimized .env configuration")
    print("2. Clear Python cache")
    print("3. Check dependencies")
    print("4. Check GPU availability")
    print("5. Run tests (optional)")
    print("\n" + "="*60)
    
    input("\nPress Enter to continue...")
    
    results = {}
    
    # Step 1: Create .env
    results['Create .env'] = create_optimized_env()
    
    # Step 2: Clear cache
    results['Clear cache'] = clear_python_cache()
    
    # Step 3: Check dependencies
    results['Check dependencies'] = check_dependencies()
    
    # Step 4: Check GPU
    results['Check GPU'] = check_gpu()
    
    # Step 5: Run tests (optional)
    print("\n" + "="*60)
    response = input("Run tests? (y/n): ")
    if response.lower() == 'y':
        results['Run tests'] = run_tests()
    
    # Print summary
    print_summary(results)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Optimization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
