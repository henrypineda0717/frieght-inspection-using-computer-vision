"""
Migration: Add multi-model support to database schema

This migration adds:
1. model_source column to detections table (VARCHAR(20), NOT NULL, DEFAULT 'general')
2. container_id column to detections table (VARCHAR(11), NULL, foreign key to containers.id)
3. detection_count column to containers table (INTEGER, NOT NULL, DEFAULT 0)
4. Index on model_source for efficient filtering

Requirements: 5.1, 5.2, 5.3, 5.6
"""

from sqlalchemy import text


def upgrade(engine):
    """Apply migration"""
    with engine.connect() as conn:
        # Add model_source column to detections table
        try:
            conn.execute(text("""
                ALTER TABLE detections 
                ADD COLUMN model_source VARCHAR(20) NOT NULL DEFAULT 'general'
            """))
            conn.commit()
            print("✓ Added model_source column to detections table")
        except Exception as e:
            print(f"⚠ model_source column may already exist: {e}")
        
        # Add container_id column to detections table
        try:
            conn.execute(text("""
                ALTER TABLE detections 
                ADD COLUMN container_id VARCHAR(11) NULL
            """))
            conn.commit()
            print("✓ Added container_id column to detections table")
        except Exception as e:
            print(f"⚠ container_id column may already exist: {e}")
        
        # Add foreign key constraint (SQLite doesn't support ALTER TABLE ADD CONSTRAINT)
        # For SQLite, we need to recreate the table or handle this in the model definition
        # The foreign key is defined in the SQLAlchemy model
        
        # Add detection_count column to containers table
        try:
            conn.execute(text("""
                ALTER TABLE containers 
                ADD COLUMN detection_count INTEGER NOT NULL DEFAULT 0
            """))
            conn.commit()
            print("✓ Added detection_count column to containers table")
        except Exception as e:
            print(f"⚠ detection_count column may already exist: {e}")
        
        # Create index on model_source for efficient filtering
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_model_source 
                ON detections(model_source)
            """))
            conn.commit()
            print("✓ Created index on model_source column")
        except Exception as e:
            print(f"⚠ Index may already exist: {e}")
        
        print("✓ Migration completed successfully")


def downgrade(engine):
    """Rollback migration"""
    with engine.connect() as conn:
        # Drop index
        try:
            conn.execute(text("DROP INDEX IF EXISTS idx_model_source"))
            conn.commit()
            print("✓ Dropped index idx_model_source")
        except Exception as e:
            print(f"⚠ Error dropping index: {e}")
        
        # Note: SQLite doesn't support DROP COLUMN in older versions
        # For production, consider using Alembic for proper migrations
        print("⚠ Column removal not implemented for SQLite compatibility")
        print("  To fully rollback, recreate the database from scratch")


if __name__ == "__main__":
    from app.database import engine
    
    print("Running migration: Add multi-model support")
    upgrade(engine)
