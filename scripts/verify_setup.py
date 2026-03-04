#!/usr/bin/env python3
"""
Verification script to check if the project is properly set up
"""
import sys
from pathlib import Path

# Add backend to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

def check_structure():
    """Check if all required directories exist"""
    print("🔍 Checking project structure...")
    
    required_dirs = [
        "backend/app/api",
        "backend/app/models",
        "backend/app/schemas",
        "backend/app/services",
        "frontend/pages",
        "frontend/assets/css",
        "frontend/assets/js",
        "frontend/assets/images",
        "models",
        "storage",
        "data",
        "scripts",
        "docs",
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        full_path = ROOT_DIR / dir_path
        if full_path.exists():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} - MISSING")
            all_exist = False
    
    return all_exist

def check_files():
    """Check if all required files exist"""
    print("\n🔍 Checking required files...")
    
    required_files = [
        "backend/app/main.py",
        "backend/app/config.py",
        "backend/app/database.py",
        "backend/requirements.txt",
        "frontend/pages/index.html",
        "frontend/pages/history.html",
        "frontend/assets/images/pti-logo.png",
        "README.md",
        "LICENSE",
        "pyproject.toml",
    ]
    
    all_exist = True
    for file_path in required_files:
        full_path = ROOT_DIR / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} - MISSING")
            all_exist = False
    
    return all_exist

def check_imports():
    """Check if Python imports work"""
    print("\n🔍 Checking Python imports...")
    
    try:
        from app.config import settings
        print(f"  ✓ Config loaded: {settings.APP_NAME} v{settings.APP_VERSION}")
    except Exception as e:
        print(f"  ✗ Config import failed: {e}")
        return False
    
    try:
        from app.database import init_db, get_db
        print("  ✓ Database module loaded")
    except Exception as e:
        print(f"  ✗ Database import failed: {e}")
        return False
    
    try:
        from app.models import Container, Inspection, Frame, Detection
        print("  ✓ Models loaded")
    except Exception as e:
        print(f"  ✗ Models import failed: {e}")
        return False
    
    try:
        from app.api import api_router
        print("  ✓ API router loaded")
    except Exception as e:
        print(f"  ✗ API router import failed: {e}")
        return False
    
    return True

def check_config():
    """Check configuration"""
    print("\n🔍 Checking configuration...")
    
    try:
        from app.config import settings
        
        print(f"  ✓ App Name: {settings.APP_NAME}")
        print(f"  ✓ Version: {settings.APP_VERSION}")
        print(f"  ✓ Database: {settings.DATABASE_URL}")
        print(f"  ✓ Storage: {settings.STORAGE_ROOT}")
        print(f"  ✓ Models: {settings.MODELS_DIR}")
        
        # Check if directories exist
        if not settings.STORAGE_ROOT.exists():
            print(f"  ⚠ Storage directory will be created: {settings.STORAGE_ROOT}")
        
        if not settings.MODELS_DIR.exists():
            print(f"  ⚠ Models directory will be created: {settings.MODELS_DIR}")
        
        return True
    except Exception as e:
        print(f"  ✗ Configuration check failed: {e}")
        return False

def main():
    """Run all checks"""
    print("=" * 60)
    print("Container Inspection System - Setup Verification")
    print("=" * 60)
    
    checks = [
        ("Project Structure", check_structure),
        ("Required Files", check_files),
        ("Python Imports", check_imports),
        ("Configuration", check_config),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} check failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {name}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All checks passed! The project is properly set up.")
        print("\nNext steps:")
        print("  1. cd backend")
        print("  2. pip install -r requirements.txt")
        print("  3. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print("  4. Open http://localhost:8000 in your browser")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
