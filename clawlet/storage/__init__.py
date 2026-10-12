"""
Storage module - Persistence backend.
"""

from clawlet.storage.sqlite import SQLiteStorage

def create_sqlite_storage(db_path: str = ":memory:"):
    """Create a SQLite storage instance."""
    return SQLiteStorage(db_path=db_path)

__all__ = [
    "SQLiteStorage",
    "create_sqlite_storage",
]
