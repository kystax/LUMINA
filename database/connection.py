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
            
            # Ensure TCP keepalives are set on DSN to keep SSL connections active
            separator = "&" if "?" in db_url else "?"
            keepalive_params = "keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=5"
            if "keepalives" not in db_url:
                db_url = f"{db_url}{separator}{keepalive_params}"

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
            "connect_timeout": 5,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
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
    """Acquire a validated, live connection from the pool.
    Tests connection liveness (SELECT 1) and automatically discards stale/dropped
    cloud SSL connections so queries never fail on first attempt.
    """
    global _DB_POOL
    if _DB_POOL is None:
        _init_pool()

    for attempt in range(3):
        if _DB_POOL is None:
            break
        try:
            conn = _DB_POOL.getconn()
            if conn is None or conn.closed != 0:
                if conn is not None:
                    _DB_POOL.putconn(conn, close=True)
                continue

            # Verify connection health with a lightweight query
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except Exception as e:
            # Cloud PostgreSQL dropped idle SSL connection — discard and retry
            if 'conn' in locals() and conn is not None:
                try:
                    _DB_POOL.putconn(conn, close=True)
                except Exception:
                    pass
            # If pool itself is broken, re-initialize
            if attempt == 1:
                _init_pool()

    return None


def release_connection(conn):
    """Return a connection to the pool.
    Closes connection if it was already marked broken/closed.
    """
    if _DB_POOL is not None and conn is not None:
        try:
            if conn.closed != 0:
                _DB_POOL.putconn(conn, close=True)
            else:
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
