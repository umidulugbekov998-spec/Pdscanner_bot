# database.py — Kengaytirilgan ma'lumotlar bazasi

import aiosqlite
import logging
from datetime import datetime

DB_PATH = "scanner_bot.db"
logger = logging.getLogger(__name__)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                is_premium  INTEGER DEFAULT 0,
                is_blocked  INTEGER DEFAULT 0,
                scan_count  INTEGER DEFAULT 0,
                joined_at   TEXT DEFAULT (datetime('now')),
                last_active TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payment_requests (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                admin_message_id INTEGER,
                status           TEXT DEFAULT 'pending',
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                message     TEXT,
                status      TEXT DEFAULT 'open',
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()
    logger.info("✅ Database initialized.")


# ── Foydalanuvchilar ──────────────────────────────────────────────────────────

async def add_or_update_user(user_id, username, full_name):
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


async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_premium(user_id, is_premium):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_premium = ? WHERE user_id = ?",
                         (1 if is_premium else 0, user_id))
        await db.commit()


async def is_premium(user_id):
    user = await get_user(user_id)
    return bool(user and user["is_premium"])


async def block_user(user_id, block=True):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?",
                         (1 if block else 0, user_id))
        await db.commit()


async def is_blocked(user_id):
    user = await get_user(user_id)
    return bool(user and user["is_blocked"])


async def increment_scan(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET scan_count = scan_count + 1 WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_blocked = 0") as cur:
            return [r[0] for r in await cur.fetchall()]


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY joined_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            r = await cur.fetchone(); return r[0] if r else 0


async def get_premium_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_premium=1") as cur:
            r = await cur.fetchone(); return r[0] if r else 0


async def get_active_today():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE date(last_active)=date('now')"
        ) as cur:
            r = await cur.fetchone(); return r[0] if r else 0


# ── Sozlamalar ────────────────────────────────────────────────────────────────

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value))
        await db.commit()


async def get_setting(key, default=""):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            r = await cur.fetchone(); return r[0] if r else default


# ── To'lov so'rovlari ─────────────────────────────────────────────────────────

async def create_payment_request(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO payment_requests (user_id) VALUES (?)", (user_id,))
        await db.commit()
        return cur.lastrowid


async def set_payment_admin_message(request_id, admin_message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payment_requests SET admin_message_id=? WHERE id=?",
                         (admin_message_id, request_id))
        await db.commit()


async def get_payment_request(request_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM payment_requests WHERE id=?", (request_id,)) as cur:
            r = await cur.fetchone(); return dict(r) if r else None


async def update_payment_status(request_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payment_requests SET status=? WHERE id=?", (status, request_id))
        await db.commit()


# ── Yordam so'rovlari ─────────────────────────────────────────────────────────

async def create_support_ticket(user_id, message):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO support_tickets (user_id, message) VALUES (?,?)", (user_id, message))
        await db.commit()
        return cur.lastrowid
