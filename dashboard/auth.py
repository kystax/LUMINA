"""
LUMINA - Auth Module
Matches the calling convention used throughout the existing codebase:

    login_user(username, password)
        → (True,  user_dict)   on success
        → (False, error_str)   on failure

    register_user(username, email, password, user_type)
        → (True,  "Account created!")  on success
        → (False, error_str)           on failure
"""
import sys
import os
from database.connection import get_connection, release_connection
import secrets
import hashlib


# Add project root (parent of "dashboard") to sys.path so "database" is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────
# PASSWORD HELPERS
# ─────────────────────────────────────────────

def _store_hash(password: str) -> str:
    """Return a storable  salt:hash  string."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{pw_hash}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a plain password against a stored  salt:hash  string."""
    try:
        if ":" not in stored:
            return False
        salt, pw_hash = stored.split(":", 1)
        computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return computed == pw_hash
    except Exception:
        return False


# ─────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────

def register_user(
    username: str,
    email: str | None = None,
    password: str = "",
    user_type: str = "individual"
) -> tuple:
    """
    Register a new user.

    Returns:
        (True,  "Account created!")   — success
        (False, "error message")      — failure
    """
    conn = get_connection()
    if not conn:
        return False, "Database connection failed."

    cur = None
    try:
        cur = conn.cursor()

        # Check username taken
        cur.execute(
            "SELECT user_id FROM users WHERE username = %s", (username,)
        )
        if cur.fetchone():
            return False, "Username already taken — please choose another."

        # Check email taken (if provided)
        if email:
            cur.execute(
                "SELECT user_id FROM users WHERE email = %s", (email,)
            )
            if cur.fetchone():
                return False, "Email already registered."

        password_hash = _store_hash(password)

        cur.execute("""
            INSERT INTO users (username, email, password_hash, user_type)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id
        """, (username, email, password_hash, user_type))

        row = cur.fetchone()
        user_id = row[0] if row else None
        conn.commit()
        print(
            f"[LUMINA Auth] Registered: {username} (ID {user_id}, type={user_type})")
        return True, "Account created!"

    except Exception as e:
        conn.rollback()
        print(f"[LUMINA Auth] Registration error: {e}")
        return False, f"Registration failed: {e}"
    finally:
        if cur:
            cur.close()
        release_connection(conn)


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

def login_user(username: str, password: str) -> tuple:
    """
    Authenticate a user.

    Returns:
        (True,  {"user_id": int, "username": str, "user_type": str, "email": str})
        (False, "error message")
    """
    conn = get_connection()
    if not conn:
        return False, "Database connection failed."

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, username, password_hash, user_type, email
            FROM users
            WHERE username = %s
        """, (username,))
        row = cur.fetchone()

        if not row:
            return False, "Invalid username or password."

        user_id, db_username, password_hash, user_type, email = row

        if not _verify_password(password, password_hash):
            return False, "Invalid username or password."

        # Update last login timestamp
        cur.execute(
            "UPDATE users SET last_login = NOW() WHERE user_id = %s",
            (user_id,)
        )
        conn.commit()

        print(
            f"[LUMINA Auth] Login: {username} (ID {user_id}, type={user_type})")
        return True, {
            "user_id":   user_id,
            "username":  db_username,
            "user_type": user_type or "individual",
            "email":     email or "",
        }

    except Exception as e:
        print(f"[LUMINA Auth] Login error: {e}")
        return False, f"Login failed: {e}"
    finally:
        if cur:
            cur.close()
        release_connection(conn)


# ─────────────────────────────────────────────
# HELPERS (used by settings page etc.)
# ─────────────────────────────────────────────

def get_user_by_id(user_id: int) -> dict | None:
    """Return user details by ID, or None if not found."""
    conn = get_connection()
    if not conn:
        return None
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, username, email, user_type, created_at, last_login
            FROM users WHERE user_id = %s
        """, (user_id,))
        row = cur.fetchone()
        if row:
            return {
                "user_id":    row[0],
                "username":   row[1],
                "email":      row[2] or "",
                "user_type":  row[3] or "individual",
                "created_at": row[4],
                "last_login": row[5],
            }
        return None
    except Exception as e:
        print(f"[LUMINA Auth] get_user_by_id error: {e}")
        return None
    finally:
        if cur:
            cur.close()
        release_connection(conn)


def update_password(user_id: int, new_password: str) -> tuple:
    """
    Update a user's password.
    Returns (True, "Updated") or (False, error_str).
    """
    conn = get_connection()
    if not conn:
        return False, "Database connection failed."
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (_store_hash(new_password), user_id)
        )
        conn.commit()
        return True, "Password updated."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        if cur:
            cur.close()
        release_connection(conn)
