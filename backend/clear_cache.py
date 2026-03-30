"""
Clear Python cache files (.pyc and __pycache__ directories)
"""
import os
import shutil
from pathlib import Path

def clear_cache(root_dir="."):
    """Clear all Python cache files and directories."""
    root_path = Path(root_dir)
    
    # Count removed items
    pycache_count = 0
    pyc_count = 0
    
    print("=" * 60)
    print("Clearing Python Cache Files")
    print("=" * 60)
    print()
    
    # Remove __pycache__ directories
    for pycache_dir in root_path.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache_dir)
            pycache_count += 1
            print(f"✓ Removed: {pycache_dir}")
        except Exception as e:
            print(f"✗ Failed to remove {pycache_dir}: {e}")
    
    # Remove .pyc files
    for pyc_file in root_path.rglob("*.pyc"):
        try:
            pyc_file.unlink()
            pyc_count += 1
            print(f"✓ Removed: {pyc_file}")
        except Exception as e:
            print(f"✗ Failed to remove {pyc_file}: {e}")
    
    print()
    print("=" * 60)
    print(f"Cache Clearing Complete")
    print(f"  __pycache__ directories removed: {pycache_count}")
    print(f"  .pyc files removed: {pyc_count}")
    print("=" * 60)
    print()
    print("Now restart your server:")
    print("  uvicorn app.main:app --reload")
    print()

if __name__ == "__main__":
    clear_cache()
