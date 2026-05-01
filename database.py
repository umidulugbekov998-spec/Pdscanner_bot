"""
database.py — Async SQLite database handler using aiosqlite.
Manages users, admin settings, and payment verification.
"""

import aiosqlite
import logging
from datetime import datetime

DB_PATH = "scanner_bot.db"

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  INITIALIZATION
# ─────────────────────────────────────────────

async def init_db():
    """Create all required tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table: stores every user who starts the bot
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                is_premium  INTEGER DEFAULT 0,
                joined_at   TEXT DEFAULT (datetime('now')),
                last_active TEXT DEFAULT (datetime('now'))
            )
        """)

        # Admin settings table: key-value store for bot configuration
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Payment requests table: tracks pending premium upgrade requests
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payment_requests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                admin_message_id INTEGER,
                status          TEXT DEFAULT 'pending',
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.commit()
    logger.info("✅ Database initialized successfully.")


# ─────────────────────────────────────────────
#  USER MANAGEMENT
# ─────────────────────────────────────────────

async def add_or_update_user(user_id: int, username: str, full_name: str):
    """Register a new user or update their last_active timestamp."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username    = excluded.username,
                full_name   = excluded.full_name,
                last_active = datetime('now')
        """, (user_id, username or "", full_name or ""))
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    """Fetch a single user record by user_id. Returns None if not found."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def set_premium(user_id: int, is_premium: bool):
    """Upgrade or downgrade a user's premium status."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_premium = ? WHERE user_id = ?",
            (1 if is_premium else 0, user_id)
        )
        await db.commit()


async def is_premium(user_id: int) -> bool:
    """Quick check: is this user premium?"""
    user = await get_user(user_id)
    return bool(user and user["is_premium"])


async def get_all_user_ids() -> list[int]:
    """Return a list of all user_ids for broadcast messages."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_user_count() -> int:
    """Return the total number of registered users."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_premium_count() -> int:
    """Return the total number of premium users."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# ─────────────────────────────────────────────
#  ADMIN SETTINGS
# ─────────────────────────────────────────────

async def set_setting(key: str, value: str):
    """Upsert a key-value setting (e.g., payment card number)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()


async def get_setting(key: str, default: str = "") -> str:
    """Retrieve a setting value by key. Returns default if not set."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default


# ─────────────────────────────────────────────
#  PAYMENT REQUESTS
# ─────────────────────────────────────────────

async def create_payment_request(user_id: int) -> int:
    """Insert a new pending payment request. Returns the new request id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO payment_requests (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()
        return cursor.lastrowid


async def set_payment_admin_message(request_id: int, admin_message_id: int):
    """Store the admin-side message_id so we can reference it later."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payment_requests SET admin_message_id = ? WHERE id = ?",
            (admin_message_id, request_id)
        )
        await db.commit()


async def get_payment_request(request_id: int) -> dict | None:
    """Fetch a payment request by its id."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payment_requests WHERE id = ?", (request_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_payment_status(request_id: int, status: str):
    """Update the status of a payment request: 'approved' or 'declined'."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payment_requests SET status = ? WHERE id = ?",
            (status, request_id)
        )
        await db.commit()
