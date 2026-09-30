"""SQLite слой на aiosqlite. Все времена — unix timestamp (int, UTC)."""
from __future__ import annotations

import time

import aiosqlite

import config


def _now() -> int:
    return int(time.time())


async def init_db() -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                added_at INTEGER
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                username TEXT,
                full_name TEXT,
                added_at INTEGER
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS restrictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                interval_minutes INTEGER NOT NULL,
                last_message_at INTEGER,
                created_at INTEGER,
                UNIQUE(user_id, chat_id)
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                until INTEGER NOT NULL,
                created_at INTEGER,
                UNIQUE(user_id, chat_id)
            )"""
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                created_at INTEGER
            )"""
        )
        # Суперадмин всегда в таблице admins (неудаляемый — проверяется в хендлерах)
        await db.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_at) VALUES (?, ?)",
            (config.SUPER_ADMIN_ID, _now()),
        )
        await db.commit()


# ---------- admins ----------

async def is_admin(user_id: int) -> bool:
    if user_id == config.SUPER_ADMIN_ID:
        return True
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone() is not None


async def get_admins() -> list[aiosqlite.Row]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY user_id") as cur:
            return await cur.fetchall()


async def add_admin(user_id: int, username: str | None = None,
                    full_name: str | None = None) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO admins (user_id, username, full_name, added_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, username, full_name, _now()),
        )
        await db.commit()


async def remove_admin(user_id: int) -> None:
    if user_id == config.SUPER_ADMIN_ID:
        return  # суперадмин неудаляем
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()


# ---------- members ----------

async def get_members(limit: int = 1000, offset: int = 0) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM members ORDER BY full_name COLLATE NOCASE, user_id "
            "LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            return await cur.fetchall()


async def count_members() -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM members") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_member(user_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM members WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone()


async def add_member(user_id: int, full_name: str,
                     username: str | None = None,
                     chat_id: int | None = None) -> bool:
    """Возвращает False если дубликат."""
    try:
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute(
                """INSERT INTO members (user_id, chat_id, username, full_name, added_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, chat_id or config.CHAT_ID, username, full_name, _now()),
            )
            await db.commit()
        return True
    except Exception:
        return False


async def delete_member(user_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM members WHERE user_id = ?", (user_id,))
        await db.execute(
            "DELETE FROM restrictions WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM mutes WHERE user_id = ?", (user_id,))
        await db.commit()


# ---------- restrictions ----------

async def get_restriction(user_id: int,
                          chat_id: int | None = None) -> aiosqlite.Row | None:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM restrictions WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        ) as cur:
            return await cur.fetchone()


async def set_restriction(user_id: int, interval_minutes: int,
                          chat_id: int | None = None) -> None:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO restrictions (user_id, chat_id, interval_minutes,
                                         last_message_at, created_at)
               VALUES (?, ?, ?, NULL, ?)
               ON CONFLICT(user_id, chat_id) DO UPDATE SET
                 interval_minutes = excluded.interval_minutes,
                 last_message_at = NULL""",
            (user_id, chat_id, interval_minutes, _now()),
        )
        await db.commit()


async def remove_restriction(user_id: int,
                             chat_id: int | None = None) -> None:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM restrictions WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        await db.commit()


async def touch_last_message(user_id: int,
                             chat_id: int | None = None) -> None:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE restrictions SET last_message_at = ? "
            "WHERE user_id = ? AND chat_id = ?",
            (_now(), user_id, chat_id),
        )
        await db.commit()


# ---------- mutes ----------

async def get_mute(user_id: int,
                   chat_id: int | None = None) -> aiosqlite.Row | None:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM mutes WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        ) as cur:
            row = await cur.fetchone()
            if row and row["until"] <= _now():
                # истёк — чистим на месте
                await db.execute(
                    "DELETE FROM mutes WHERE user_id = ? AND chat_id = ?",
                    (user_id, chat_id),
                )
                await db.commit()
                return None
            return row


async def set_mute(user_id: int, duration_minutes: int,
                   chat_id: int | None = None) -> int:
    """Возвращает unix timestamp окончания."""
    chat_id = chat_id or config.CHAT_ID
    until = _now() + duration_minutes * 60
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """INSERT INTO mutes (user_id, chat_id, until, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, chat_id) DO UPDATE SET
                 until = excluded.until""",
            (user_id, chat_id, until, _now()),
        )
        await db.commit()
    return until


async def remove_mute(user_id: int, chat_id: int | None = None) -> None:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM mutes WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        await db.commit()


# ---------- violations ----------

async def log_violation(user_id: int, kind: str,
                        chat_id: int | None = None) -> None:
    """kind: 'mute' или 'slow'."""
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO violations (user_id, chat_id, kind, created_at)"
            " VALUES (?, ?, ?, ?)",
            (user_id, chat_id, kind, _now()),
        )
        await db.commit()


async def get_violation_counts(user_id: int,
                               chat_id: int | None = None) -> dict[str, int]:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT kind, COUNT(*) FROM violations"
            " WHERE user_id = ? AND chat_id = ? GROUP BY kind",
            (user_id, chat_id),
        ) as cur:
            rows = await cur.fetchall()
    counts = {"mute": 0, "slow": 0}
    for kind, n in rows:
        if kind in counts:
            counts[kind] = n
    return counts


async def get_violation_totals(
        chat_id: int | None = None) -> dict[int, int]:
    """user_id -> общее число срабатываний."""
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, COUNT(*) FROM violations"
            " WHERE chat_id = ? GROUP BY user_id",
            (chat_id,),
        ) as cur:
            return {uid: n async for uid, n in cur}


async def clear_violations(user_id: int,
                           chat_id: int | None = None) -> None:
    chat_id = chat_id or config.CHAT_ID
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM violations WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id),
        )
        await db.commit()


# ---------- restricted list ----------

async def get_restricted() -> tuple[list[dict], list[dict]]:
    """Возвращает (slow_list, mute_list), каждый элемент — dict с полями member + данные."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = _now()
        await db.execute("DELETE FROM mutes WHERE until <= ?", (now,))
        await db.commit()
        async with db.execute(
            """SELECT m.user_id, m.username, m.full_name, r.interval_minutes,
                      r.last_message_at, r.created_at
               FROM restrictions r JOIN members m ON m.user_id = r.user_id
               ORDER BY m.full_name COLLATE NOCASE"""
        ) as cur:
            slow = [dict(r) for r in await cur.fetchall()]
        async with db.execute(
            """SELECT m.user_id, m.username, m.full_name, mu.until
               FROM mutes mu JOIN members m ON m.user_id = mu.user_id
               ORDER BY mu.until"""
        ) as cur:
            mutes = [dict(r) for r in await cur.fetchall()]
    return slow, mutes
