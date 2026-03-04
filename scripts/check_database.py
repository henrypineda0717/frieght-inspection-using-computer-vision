"""
Check what's in the database
"""
import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.database import SessionLocal
from backend.app.models import Container, Inspection, Frame, Detection

def check_database():
    """Check database contents"""
    db = SessionLocal()
    
    try:
        containers = db.query(Container).all()
        inspections = db.query(Inspection).all()
        frames = db.query(Frame).all()
        detections = db.query(Detection).all()
        
        print("📊 Database Contents:")
        print(f"   Containers: {len(containers)}")
        print(f"   Inspections: {len(inspections)}")
        print(f"   Frames: {len(frames)}")
        print(f"   Detections: {len(detections)}")
        print()
        
        if containers:
            print("📦 Containers:")
            for c in containers:
                insp_count = db.query(Inspection).filter(Inspection.container_id == c.id).count()
                print(f"   - {c.id} (ISO: {c.iso_type}, Inspections: {insp_count})")
        
        if inspections:
            print("\n🔍 Inspections:")
            for i in inspections:
                print(f"   - ID {i.id}: Container {i.container_id}, Status: {i.status}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_database()
