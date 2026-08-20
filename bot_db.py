"""
bot_db.py — SQLite database layer for AnneBella Telegram Bot
Handles users, subscriptions, credit/day system, and dynamic settings.
"""
import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT    DEFAULT '',
            first_name  TEXT    DEFAULT '',
            trial_started TEXT,
            expires_at  TEXT,
            is_banned   INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS activity (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER,
            action    TEXT,
            detail    TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Users ──────────────────────────────────────────────────────────────────────

def get_user(user_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def register_user(user_id: int, username: str, first_name: str):
    """Register new user with 1-day trial. Returns existing user if already registered."""
    now = datetime.utcnow()
    trial_expires = now + timedelta(days=1)
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO users (user_id, username, first_name, trial_started, expires_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, username or "", first_name or "", now.isoformat(), trial_expires.isoformat()),
    )
    conn.commit()
    conn.close()
    return get_user(user_id)


def is_active(user: dict) -> bool:
    if not user:
        return False
    if user.get("is_banned"):
        return False
    expires_str = user.get("expires_at")
    if not expires_str:
        return False
    return datetime.utcnow() < datetime.fromisoformat(expires_str)


def add_days(user_id: int, days: int) -> datetime:
    """Add N days to a user's subscription. Creates user if missing."""
    user = get_user(user_id)
    if not user:
        register_user(user_id, "", "")
        user = get_user(user_id)

    now = datetime.utcnow()
    current_expiry_str = user.get("expires_at")
    if current_expiry_str:
        current_expiry = datetime.fromisoformat(current_expiry_str)
        base = current_expiry if current_expiry > now else now
    else:
        base = now
    new_expiry = base + timedelta(days=days)

    conn = get_conn()
    conn.execute("UPDATE users SET expires_at = ? WHERE user_id = ?", (new_expiry.isoformat(), user_id))
    conn.commit()
    conn.close()
    return new_expiry


def set_expiry(user_id: int, expiry: datetime):
    conn = get_conn()
    conn.execute("UPDATE users SET expires_at = ? WHERE user_id = ?", (expiry.isoformat(), user_id))
    conn.commit()
    conn.close()


def ban_user(user_id: int):
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unban_user(user_id: int):
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_users() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_users() -> list:
    users = get_all_users()
    return [u for u in users if is_active(u)]


def log_activity(user_id: int, action: str, detail: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO activity (user_id, action, detail) VALUES (?, ?, ?)",
        (user_id, action, detail),
    )
    conn.commit()
    conn.close()


# ── Dynamic Settings (env var overrides) ───────────────────────────────────────

def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def get_setting(key: str, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def get_all_settings() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def delete_setting(key: str):
    conn = get_conn()
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()
    conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def time_remaining(expires_at_str: str) -> str:
    if not expires_at_str:
        return "❌ No access"
    expires = datetime.fromisoformat(expires_at_str)
    now = datetime.utcnow()
    if now >= expires:
        return "❌ Expired"
    delta = expires - now
    days = delta.days
    hours, rem = divmod(int(delta.total_seconds()) % 86400, 3600)
    mins = rem // 60
    if days > 0:
        return f"✅ {days}d {hours}h {mins}m remaining"
    return f"✅ {hours}h {mins}m remaining"
