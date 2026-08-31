# database/connection.py

"""Database connection handling with a threaded connection pool.
Provides a `get_connection()` helper that returns a psycopg2 connection from the pool.
The pool is initialized on first use using environment variables or Streamlit secrets.
Supports standalone DATABASE_URL (Neon, Supabase, Render, Railway, etc.).
"""

import os
import psycopg2
from psycopg2 import pool
from pathlib import Path


def _load_env_file() -> None:
    """Load .env from the repo root into os.environ (works without python-dotenv)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    try:
        # Try python-dotenv first (cleaner, handles quotes / escaping)
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path, override=False)
        return
    except ImportError:
        pass
    # Manual fallback: parse key=value lines
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


_load_env_file()


# Global connection pool (singleton)
_DB_POOL: pool.ThreadedConnectionPool | None = None
_INIT_ATTEMPTED = False
_LAST_ERROR = None


def _get_config_val(key: str, default=None):
    """Retrieve config value safely from Streamlit secrets, environment variables, or default."""
    try:
        import streamlit as st
        # Check Streamlit secrets if available
        if hasattr(st, "secrets"):
            try:
                # 1. Direct top-level key lookup
                if key in st.secrets:
                    val = st.secrets[key]
                    if val is not None and not isinstance(val, (dict, list)):
                        return str(val).strip()
            except Exception:
                pass

            # 2. Check nested sections like [postgres] or [database] only if they are dicts
            for section in ["postgres", "database", "postgresql"]:
                try:
                    if section in st.secrets:
                        sec_obj = st.secrets[section]
                        if isinstance(sec_obj, dict) and key in sec_obj:
                            val = sec_obj[key]
                            if val is not None and not isinstance(val, (dict, list)):
                                return str(val).strip()
                except Exception:
                    pass
    except Exception:
        pass

    # 3. Environment variables fallback
    try:
        val = os.getenv(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    except Exception:
        pass

    return default


def _init_pool():
    global _DB_POOL, _INIT_ATTEMPTED, _LAST_ERROR
    _INIT_ATTEMPTED = True

    try:
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

        kwargs = {
            "minconn": 1,
            "maxconn": 10,
            "host": host,
            "port": int(port) if str(port).isdigit() else 5432,
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
        print(f"[LUMINA DB] Database connection unavailable ({e}). App running with demo/offline fallback.")
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
