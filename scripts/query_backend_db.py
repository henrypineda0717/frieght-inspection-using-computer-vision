"""
Query the backend database directly
"""
import sqlite3
from pathlib import Path

# Backend database path
db_path = Path(__file__).resolve().parent.parent / "backend" / "inspections.db"

print(f"📂 Checking database: {db_path}")
print(f"   Exists: {db_path.exists()}")
print()

if not db_path.exists():
    print("❌ Database file not found!")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Count records
cursor.execute("SELECT COUNT(*) FROM containers")
container_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM inspections")
inspection_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM frames")
frame_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM detections")
detection_count = cursor.fetchone()[0]

print("📊 Database Statistics:")
print(f"   Containers: {container_count}")
print(f"   Inspections: {inspection_count}")
print(f"   Frames: {frame_count}")
print(f"   Detections: {detection_count}")
print()

# Show containers
cursor.execute("SELECT id, iso_type FROM containers")
containers = cursor.fetchall()

if containers:
    print("📦 Containers in database:")
    for container_id, iso_type in containers:
        cursor.execute("SELECT COUNT(*) FROM inspections WHERE container_id = ?", (container_id,))
        insp_count = cursor.fetchone()[0]
        print(f"   - {container_id} (ISO: {iso_type}, Inspections: {insp_count})")
        
        if insp_count == 0:
            print(f"     ⚠️  ORPHANED - No inspections!")
    print()
    
    # Count orphaned
    orphaned = sum(1 for cid, _ in containers 
                   if cursor.execute("SELECT COUNT(*) FROM inspections WHERE container_id = ?", (cid,)).fetchone()[0] == 0)
    
    if orphaned > 0:
        print(f"⚠️  Found {orphaned} orphaned container(s)")
        print("   Run cleanup to remove them")

conn.close()
