"""
Storage module - Persistence backends.

Available backends:
- SQLiteStorage: Local SQLite database (default)
- PostgresStorage: PostgreSQL for production
"""

from clawlet.storage.sqlite import SQLiteStorage

def get_postgres():
    from clawlet.storage.postgres import PostgresStorage
    return PostgresStorage

__all__ = [
    "SQLiteStorage",
    "get_postgres",
]
