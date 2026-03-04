"""
Migration runner script

Usage:
    python -m migrations.run_migrations upgrade
    python -m migrations.run_migrations downgrade
"""

import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
import migrations.migration_001_add_multi_model_support as migration_001
import migrations.migration_002_add_iso6346_fields as migration_002


MIGRATIONS = [
    migration_001,
    migration_002,
]


def run_upgrade():
    """Run all migrations"""
    print("=" * 60)
    print("Running database migrations (upgrade)")
    print("=" * 60)
    
    for migration in MIGRATIONS:
        print(f"\n→ Running: {migration.__name__}")
        try:
            migration.upgrade(engine)
        except Exception as e:
            print(f"✗ Migration failed: {e}")
            return False
    
    print("\n" + "=" * 60)
    print("All migrations completed successfully")
    print("=" * 60)
    return True


def run_downgrade():
    """Rollback all migrations"""
    print("=" * 60)
    print("Running database migrations (downgrade)")
    print("=" * 60)
    
    for migration in reversed(MIGRATIONS):
        print(f"\n→ Rolling back: {migration.__name__}")
        try:
            migration.downgrade(engine)
        except Exception as e:
            print(f"✗ Rollback failed: {e}")
            return False
    
    print("\n" + "=" * 60)
    print("All migrations rolled back successfully")
    print("=" * 60)
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m migrations.run_migrations [upgrade|downgrade]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "upgrade":
        success = run_upgrade()
    elif command == "downgrade":
        success = run_downgrade()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python -m migrations.run_migrations [upgrade|downgrade]")
        sys.exit(1)
    
    sys.exit(0 if success else 1)
