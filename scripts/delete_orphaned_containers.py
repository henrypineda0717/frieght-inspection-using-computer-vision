"""
Delete orphaned containers from the backend database
"""
import sqlite3
from pathlib import Path

# Backend database path
db_path = Path(__file__).resolve().parent.parent / "backend" / "inspections.db"

print(f"📂 Database: {db_path}")
print()

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Find orphaned containers
cursor.execute("""
    SELECT c.id, c.iso_type 
    FROM containers c
    LEFT JOIN inspections i ON c.id = i.container_id
    GROUP BY c.id
    HAVING COUNT(i.id) = 0
""")

orphaned = cursor.fetchall()

if not orphaned:
    print("✅ No orphaned containers found!")
    conn.close()
    exit(0)

print(f"Found {len(orphaned)} orphaned container(s):")
for container_id, iso_type in orphaned:
    print(f"   - {container_id} (ISO: {iso_type})")

print()
response = input("Delete these containers? (yes/no): ")

if response.lower() in ['yes', 'y']:
    for container_id, _ in orphaned:
        cursor.execute("DELETE FROM containers WHERE id = ?", (container_id,))
        print(f"   ✅ Deleted: {container_id}")
    
    conn.commit()
    print()
    print(f"✅ Successfully deleted {len(orphaned)} container(s)")
else:
    print("❌ Cancelled")

conn.close()
