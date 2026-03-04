"""
Check ISO 6346 fields in containers table
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

# Check table schema
cursor.execute("PRAGMA table_info(containers)")
columns = cursor.fetchall()

print("📋 Containers table schema:")
for col in columns:
    col_id, name, col_type, not_null, default, pk = col
    print(f"   - {name} ({col_type})")
print()

# Show containers with ISO 6346 fields
cursor.execute("""
    SELECT id, owner_code, category, serial_number, check_digit, iso_type, detection_count
    FROM containers
""")
containers = cursor.fetchall()

if containers:
    print("📦 Containers with ISO 6346 fields:")
    for container_id, owner, cat, serial, check, iso_type, count in containers:
        print(f"\n   Container ID: {container_id}")
        print(f"   ├─ Owner Code: {owner or 'N/A'}")
        print(f"   ├─ Category: {cat or 'N/A'}")
        print(f"   ├─ Serial Number: {serial or 'N/A'}")
        print(f"   ├─ Check Digit: {check if check is not None else 'N/A'}")
        print(f"   ├─ ISO Type: {iso_type or 'N/A'}")
        print(f"   └─ Detection Count: {count}")

conn.close()
