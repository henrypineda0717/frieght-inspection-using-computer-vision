#!/usr/bin/env python3
"""
Initialization script for Container Inspection System with Database
"""
import sys
from pathlib import Path

# Add backend to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

def check_dependencies():
    """Check if required packages are installed"""
    print("Checking dependencies...")
    
    required = [
        'fastapi',
        'sqlalchemy',
        'cv2',
        'numpy',
        'ultralytics',
    ]
    
    missing = []
    for package in required:
        try:
            if package == 'cv2':
                import cv2
            else:
                __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print("\n⚠ Missing dependencies. Install with:")
        print("  pip install -r requirements.txt")
        return False
    
    print("\n✓ All dependencies installed\n")
    return True


def init_database():
    """Initialize the database"""
    print("Initializing database...")
    
    try:
        from app.database import init_db
        from app.config import settings
        
        init_db()
        
        # Check if database file exists (for SQLite)
        if "sqlite" in settings.DATABASE_URL:
            db_path = ROOT_DIR / "inspections.db"
            if db_path.exists():
                print(f"  ✓ Database created at: {db_path}")
                print(f"  ✓ Database size: {db_path.stat().st_size} bytes")
            else:
                print(f"  ✓ Database initialized: {settings.DATABASE_URL}")
        else:
            print(f"  ✓ Database initialized: {settings.DATABASE_URL}")
        
        print("\n✓ Database initialized\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to initialize database: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_storage_dirs():
    """Create storage directories"""
    print("Creating storage directories...")
    
    try:
        from app.config import settings
        
        # Create storage root
        settings.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Storage directory: {settings.STORAGE_ROOT}")
        
        # Create models directory
        settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Models directory: {settings.MODELS_DIR}")
        
        # Create data directory
        data_dir = ROOT_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Data directory: {data_dir}")
        
        print("\n✓ Storage directories created\n")
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to create storage directories: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_models():
    """Check if YOLO models exist"""
    print("Checking YOLO models...")
    
    try:
        from app.config import settings
        
        models = {
            'yolov8n.pt': 'Generic YOLO model',
            'pti_best.pt': 'Container-specific model (optional)'
        }
        
        found = []
        missing = []
        
        for model, desc in models.items():
            path = settings.MODELS_DIR / model
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"  ✓ {model} ({desc}) - {size_mb:.1f} MB")
                found.append(model)
            else:
                print(f"  ⚠ {model} ({desc}) - NOT FOUND")
                missing.append(model)
        
        if 'yolov8n.pt' not in found:
            print("\n⚠ Generic YOLO model missing. It will be downloaded on first run.")
        
        if 'pti_best.pt' not in found:
            print("⚠ Container-specific model missing. Train it with: python scripts/train_yolo.py")
        
        print()
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to check models: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_startup_instructions():
    """Print instructions to start the system"""
    print("=" * 60)
    print("INITIALIZATION COMPLETE")
    print("=" * 60)
    print()
    print("To start the system:")
    print()
    print("  1. Navigate to backend directory:")
    print("     cd backend")
    print()
    print("  2. Start the backend:")
    print("     uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print()
    print("  3. Open your browser:")
    print("     - Live Analysis: http://localhost:8000/")
    print("     - History Viewer: http://localhost:8000/history.html")
    print("     - API Docs: http://localhost:8000/docs")
    print()
    print("For more information, see:")
    print("  - SETUP_COMPLETE.md")
    print("  - QUICK_REFERENCE.md")
    print("  - docs/guides/GETTING_STARTED.md")
    print()


def main():
    """Main initialization routine"""
    print("=" * 60)
    print("Container Inspection System - Initialization")
    print("=" * 60)
    print()
    
    steps = [
        ("Checking dependencies", check_dependencies),
        ("Initializing database", init_database),
        ("Creating storage directories", create_storage_dirs),
        ("Checking YOLO models", check_models),
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n✗ Initialization failed at: {step_name}")
            print("Please fix the errors above and try again.")
            sys.exit(1)
    
    print_startup_instructions()


if __name__ == "__main__":
    main()
