# database/connection.py

"""Database connection handling with a threaded connection pool.
Provides a `get_connection()` helper that returns a psycopg2 connection from the pool.
The pool is initialized on first import using environment variables.
"""

import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

# Global connection pool (singleton)
_DB_POOL: pool.ThreadedConnectionPool | None = None

def _init_pool():
    global _DB_POOL
    if _DB_POOL is None:
        try:
            _DB_POOL = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", 5432),
                dbname=os.getenv("DB_NAME", "lumina_db"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD"),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create DB connection pool: {e}")

def get_connection():
    """Acquire a connection from the pool.
    Caller must close the connection when done (returns it to the pool).
    """
    if _DB_POOL is None:
        _init_pool()
    try:
        if _DB_POOL is not None:
            return _DB_POOL.getconn()
        raise RuntimeError("Database pool not initialized.")
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}")

def release_connection(conn):
    """Return a connection to the pool.
    No-op if pool not initialized.
    """
    if _DB_POOL is not None and conn is not None:
        _DB_POOL.putconn(conn)

if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("Connected to lumina_db successfully!")
        release_connection(conn)
