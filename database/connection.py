# database/connection.py

"""Database connection handling with a threaded connection pool.
Provides a `get_connection()` helper that returns a psycopg2 connection from the pool.
The pool is initialized on first use using environment variables or Streamlit secrets.
Supports standalone DATABASE_URL (Neon, Supabase, Render, Railway, etc.).
"""

import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

# Global connection pool (singleton)
_DB_POOL: pool.ThreadedConnectionPool | None = None
_INIT_ATTEMPTED = False
_LAST_ERROR = None


def _get_config_val(key: str, default=None):
    """Retrieve config value from Streamlit secrets, environment variables, or default."""
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if key in st.secrets:
                return str(st.secrets[key])
            # Check nested sections like [postgres] or [database]
            for section in ["postgres", "database", "postgresql"]:
                if section in st.secrets and key in st.secrets[section]:
                    return str(st.secrets[section][key])
    except Exception:
        pass
    return os.getenv(key, default)


def _init_pool():
    global _DB_POOL, _INIT_ATTEMPTED, _LAST_ERROR
    _INIT_ATTEMPTED = True

    # 1. Try DATABASE_URL / POSTGRES_URL first (common for cloud DBs)
    db_url = _get_config_val("DATABASE_URL") or _get_config_val("POSTGRES_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        try:
            _DB_POOL = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=db_url
            )
            _LAST_ERROR = None
            print("[LUMINA DB] Connection pool created via DATABASE_URL.")
            return
        except Exception as e:
            _LAST_ERROR = str(e)
            print(f"[LUMINA DB] Failed to create pool from DATABASE_URL: {e}")

    # 2. Try individual parameters
    host = _get_config_val("DB_HOST", "localhost")
    port = _get_config_val("DB_PORT", "5432")
    dbname = _get_config_val("DB_NAME", "lumina_db")
    user = _get_config_val("DB_USER", "postgres")
    password = _get_config_val("DB_PASSWORD", None)
    sslmode = _get_config_val("DB_SSLMODE", None)

    # If no password or localhost on cloud without explicit intent, attempt safely
    try:
        kwargs = {
            "minconn": 1,
            "maxconn": 10,
            "host": host,
            "port": int(port),
            "dbname": dbname,
            "user": user,
            "connect_timeout": 3,
        }
        if password:
            kwargs["password"] = password
        if sslmode:
            kwargs["sslmode"] = sslmode

        _DB_POOL = pool.ThreadedConnectionPool(**kwargs)
        _LAST_ERROR = None
        print(f"[LUMINA DB] Connection pool created for {user}@{host}:{port}/{dbname}.")
    except Exception as e:
        _LAST_ERROR = str(e)
        print(f"[LUMINA DB] Notice: Database connection unavailable ({e}). Running in offline/demo mode.")
        _DB_POOL = None


def get_connection():
    """Acquire a connection from the pool.
    Returns None if database is unavailable or not configured.
    Caller must return connection with release_connection(conn).
    """
    global _DB_POOL
    if _DB_POOL is None:
        _init_pool()
    if _DB_POOL is not None:
        try:
            return _DB_POOL.getconn()
        except Exception as e:
            print(f"[LUMINA DB] getconn failed: {e}")
            return None
    return None


def release_connection(conn):
    """Return a connection to the pool.
    No-op if pool not initialized or conn is None.
    """
    if _DB_POOL is not None and conn is not None:
        try:
            _DB_POOL.putconn(conn)
        except Exception:
            pass


def is_db_connected() -> bool:
    """Check if database is currently reachable."""
    conn = get_connection()
    if conn:
        release_connection(conn)
        return True
    return False


def get_last_error() -> str | None:
    """Return the last database connection error message if any."""
    return _LAST_ERROR


if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("Connected to lumina_db successfully!")
        release_connection(conn)
    else:
        print(f"Connection failed: {_LAST_ERROR}")
