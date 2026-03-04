"""
Cleanup script to remove orphaned containers from the database
"""
import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.app.database import SessionLocal
from backend.app.models import Container, Inspection

def cleanup_orphaned_containers():
    """Remove containers that have no associated inspections"""
    db = SessionLocal()
    
    try:
        # Find all containers
        all_containers = db.query(Container).all()
        deleted_count = 0
        
        print(f"Found {len(all_containers)} containers in database")
        
        for container in all_containers:
            inspection_count = db.query(Inspection).filter(
                Inspection.container_id == container.id
            ).count()
            
            if inspection_count == 0:
                print(f"  Deleting orphaned container: {container.id}")
                db.delete(container)
                deleted_count += 1
            else:
                print(f"  Keeping container: {container.id} ({inspection_count} inspections)")
        
        db.commit()
        
        print(f"\n✅ Cleanup complete!")
        print(f"   Deleted: {deleted_count} orphaned container(s)")
        print(f"   Remaining: {len(all_containers) - deleted_count} container(s)")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🧹 Starting orphaned container cleanup...\n")
    cleanup_orphaned_containers()
