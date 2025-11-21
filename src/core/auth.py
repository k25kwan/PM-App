import os
import sqlite3
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

# Default local DB path (can be overridden with LOCAL_DB_PATH env var)
DB_PATH = os.getenv('LOCAL_DB_PATH', str(Path(__file__).parent.parent.parent / 'data' / 'pm_app_local.db'))


def _get_conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    cn = _get_conn()
    cur = cn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT UNIQUE NOT NULL,
        password_hash BLOB NOT NULL,
        salt BLOB NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    cn.commit()
    cn.close()


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200_000)


def create_user(username: str, email: str, password: str) -> int:
    init_db()
    salt = secrets.token_bytes(16)
    pwd_hash = _hash_password(password, salt)
    cn = _get_conn()
    cur = cn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        cur.execute(
            "INSERT INTO users (username, email, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, email.lower(), pwd_hash, salt, now),
        )
        cn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        user_id = 0
    finally:
        cn.close()
    return user_id


def verify_user(email: str, password: str) -> int:
    init_db()
    cn = _get_conn()
    cur = cn.cursor()
    cur.execute("SELECT id, password_hash, salt, username FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    cn.close()
    if not row:
        return 0
    salt = row['salt']
    stored = row['password_hash']
    calc = _hash_password(password, salt)
    if secrets.compare_digest(calc, stored):
        return int(row['id'])
    return 0


def get_user(user_id: int):
    init_db()
    cn = _get_conn()
    cur = cn.cursor()
    cur.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    cn.close()
    if not row:
        return None
    return dict(row)


def require_login(st):
    """Enforce login on Streamlit pages. Call `require_login(st)` at the top of a page."""
    user_id = st.session_state.get('user_id')
    if not user_id:
        st.warning("Please log in or create an account on the Home page to continue.")
        st.stop()


__all__ = [
    'init_db',
    'create_user',
    'verify_user',
    'get_user',
    'require_login',
]
