"""
Migration 002: Add ISO 6346 fields to containers table

Adds owner_code, category, serial_number, and check_digit columns
to support proper ISO 6346 container identification.
"""
from sqlalchemy import text


def upgrade(engine):
    """
    Add ISO 6346 fields to containers table.
    
    Args:
        engine: SQLAlchemy engine
    """
    print("🔄 Running migration 002: Add ISO 6346 fields to containers")
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("PRAGMA table_info(containers)"))
        columns = [row[1] for row in result]
        
        # Add owner_code column if it doesn't exist
        if 'owner_code' not in columns:
            conn.execute(text("ALTER TABLE containers ADD COLUMN owner_code VARCHAR(3)"))
            conn.commit()
            print("   ✅ Added owner_code column")
        else:
            print("   ⏭️  owner_code column already exists")
        
        # Add category column if it doesn't exist
        if 'category' not in columns:
            conn.execute(text("ALTER TABLE containers ADD COLUMN category VARCHAR(1)"))
            conn.commit()
            print("   ✅ Added category column")
        else:
            print("   ⏭️  category column already exists")
        
        # Add serial_number column if it doesn't exist
        if 'serial_number' not in columns:
            conn.execute(text("ALTER TABLE containers ADD COLUMN serial_number VARCHAR(6)"))
            conn.commit()
            print("   ✅ Added serial_number column")
        else:
            print("   ⏭️  serial_number column already exists")
        
        # Add check_digit column if it doesn't exist
        if 'check_digit' not in columns:
            conn.execute(text("ALTER TABLE containers ADD COLUMN check_digit INTEGER"))
            conn.commit()
            print("   ✅ Added check_digit column")
        else:
            print("   ⏭️  check_digit column already exists")
        
        # Populate new fields for existing containers with valid IDs
        result = conn.execute(text("SELECT id FROM containers WHERE id != 'UNKNOWN' AND LENGTH(id) = 11"))
        containers = result.fetchall()
        
        for (container_id,) in containers:
            # Parse ISO 6346 format: AAAU123456C
            # AAA = owner code (3 letters)
            # U = category (1 letter)
            # 123456 = serial number (6 digits)
            # C = check digit (1 digit)
            if len(container_id) == 11:
                owner_code = container_id[:3]
                category = container_id[3]
                serial_number = container_id[4:10]
                check_digit = int(container_id[10]) if container_id[10].isdigit() else None
                
                conn.execute(
                    text(
                        """
                        UPDATE containers 
                        SET owner_code = :owner_code, category = :category, 
                            serial_number = :serial_number, check_digit = :check_digit
                        WHERE id = :id
                        """
                    ),
                    {
                        "owner_code": owner_code,
                        "category": category,
                        "serial_number": serial_number,
                        "check_digit": check_digit,
                        "id": container_id
                    }
                )
                conn.commit()
                print(f"   📦 Updated {container_id}: owner={owner_code}, category={category}")
        
        print("✅ Migration 002 completed successfully")


def downgrade(engine):
    """
    Remove ISO 6346 fields from containers table.
    
    Note: SQLite doesn't support DROP COLUMN, so this is a no-op.
    In production, you would need to recreate the table without these columns.
    
    Args:
        engine: SQLAlchemy engine
    """
    print("⚠️  Migration 002 downgrade: SQLite doesn't support DROP COLUMN")
    print("   To fully rollback, you would need to recreate the containers table")


if __name__ == "__main__":
    # Run migration on default database
    from pathlib import Path
    import sqlite3
    
    db_path = Path(__file__).parent.parent / "inspections.db"
    if db_path.exists():
        # For standalone execution, use direct SQLite connection
        from sqlalchemy import create_engine
        engine = create_engine(f"sqlite:///{db_path}")
        upgrade(engine)
    else:
        print(f"❌ Database not found: {db_path}")
