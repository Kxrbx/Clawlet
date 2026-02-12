"""
Storage module - Persistence backends.

Available backends:
- SQLiteStorage: Local SQLite database (default)
- PostgresStorage: PostgreSQL for production
"""

from clawlet.storage.sqlite import SQLiteStorage

def create_sqlite_storage(db_path: str = ":memory:"):
    """Create a SQLite storage instance."""
    return SQLiteStorage(db_path=db_path)

def create_postgres_storage(
    host: str = "localhost",
    port: int = 5432,
    database: str = "clawlet",
    user: str = "postgres",
    password: str = "",
):
    """Create a PostgreSQL storage instance."""
    from clawlet.storage.postgres import PostgresStorage
    return PostgresStorage(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )

__all__ = [
    "SQLiteStorage",
    "create_sqlite_storage",
    "create_postgres_storage",
]
