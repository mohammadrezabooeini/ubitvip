from typing import List, Optional

import aiosqlite
import sqlite3

from config import DB_NAME, logger

UserRow = aiosqlite.Row


class Database:
    """
    SQLite access layer for VIP users.
    """

    def __init__(self, db_name: str = DB_NAME) -> None:
        self._db_name: str = db_name

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self._db_name, timeout=30.0)

    async def _prepare(self, conn: aiosqlite.Connection) -> None:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout = 5000")

    async def init(self) -> None:
        """Create the users table and enable WAL."""
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute("PRAGMA synchronous=NORMAL")
                await conn.execute("PRAGMA foreign_keys=ON")
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users(
                        telegram_id   INTEGER PRIMARY KEY,
                        username      TEXT,
                        first_name    TEXT,
                        yubit_uid     TEXT UNIQUE,
                        vip_status    TEXT NOT NULL DEFAULT 'inactive',
                        balance       REAL DEFAULT 0,
                        invite_link   TEXT,
                        joined_at     TEXT,
                        last_check    TEXT,
                        last_warning  TEXT,
                        warning_count INTEGER DEFAULT 0
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bot_users(
                        telegram_id INTEGER PRIMARY KEY,
                        username    TEXT,
                        first_name  TEXT,
                        first_seen  TEXT NOT NULL DEFAULT (datetime('now')),
                        last_seen   TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS support_messages(
                        admin_chat_id    INTEGER NOT NULL,
                        admin_message_id INTEGER NOT NULL,
                        user_telegram_id INTEGER NOT NULL,
                        created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                        PRIMARY KEY(admin_chat_id, admin_message_id)
                    )
                    """
                )
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS campaign(
                        id                INTEGER PRIMARY KEY CHECK(id=1),
                        source_chat_id    INTEGER NOT NULL,
                        source_message_id INTEGER NOT NULL,
                        updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                await conn.commit()

            logger.info("Database initialized successfully.")

        except Exception:
            logger.exception("Database init error")
            raise

    async def register_user(
        self,
        telegram_id: int,
        username: Optional[str],
        first_name: Optional[str],
        yubit_uid: str,
        balance: float,
        invite_link: str,
    ) -> str:
        """
        Insert a new user or reactivate an inactive one.

        Returns:
            created | reactivated | already_active | uid_taken
        """
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute("BEGIN IMMEDIATE")

                cursor = await conn.execute(
                    "SELECT * FROM users WHERE telegram_id=?",
                    (telegram_id,),
                )
                existing = await cursor.fetchone()

                uid_cursor = await conn.execute(
                    """
                    SELECT telegram_id
                    FROM users
                    WHERE yubit_uid=?
                    """,
                    (yubit_uid,),
                )
                uid_owner = await uid_cursor.fetchone()

                if uid_owner is not None and uid_owner["telegram_id"] != telegram_id:
                    await conn.rollback()
                    return "uid_taken"

                if existing is not None:
                    if existing["vip_status"] == "active":
                        await conn.rollback()
                        return "already_active"

                    await conn.execute(
                        """
                        UPDATE users
                        SET
                            username=?,
                            first_name=?,
                            yubit_uid=?,
                            vip_status='active',
                            balance=?,
                            invite_link=?,
                            joined_at=datetime('now'),
                            last_check=NULL,
                            last_warning=NULL,
                            warning_count=0
                        WHERE telegram_id=?
                        """,
                        (
                            username,
                            first_name,
                            yubit_uid,
                            balance,
                            invite_link,
                            telegram_id,
                        ),
                    )
                    await conn.commit()
                    logger.info(
                        "User reactivated: telegram_id=%s, uid=%s",
                        telegram_id,
                        yubit_uid,
                    )
                    return "reactivated"

                await conn.execute(
                    """
                    INSERT INTO users(
                        telegram_id,
                        username,
                        first_name,
                        yubit_uid,
                        vip_status,
                        balance,
                        invite_link,
                        joined_at
                    )
                    VALUES(
                        ?, ?, ?, ?, 'active', ?, ?, datetime('now')
                    )
                    """,
                    (
                        telegram_id,
                        username,
                        first_name,
                        yubit_uid,
                        balance,
                        invite_link,
                    ),
                )
                await conn.commit()

            logger.info(
                "User added: telegram_id=%s, uid=%s",
                telegram_id,
                yubit_uid,
            )
            return "created"

        except sqlite3.IntegrityError:
            logger.warning(
                "UID already taken during register: uid=%s telegram_id=%s",
                yubit_uid,
                telegram_id,
            )
            return "uid_taken"
        except Exception:
            logger.exception("Register user error")
            raise

    async def get_user(
        self,
        telegram_id: int,
    ) -> Optional[UserRow]:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE telegram_id=?",
                    (telegram_id,),
                )
                return await cursor.fetchone()

        except Exception:
            logger.exception("Get user error")
            raise

    async def get_user_by_uid(
        self,
        uid: str,
    ) -> Optional[UserRow]:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE yubit_uid=?",
                    (uid,),
                )
                return await cursor.fetchone()

        except Exception:
            logger.exception("Get user by UID error")
            raise

    async def get_all_active_users(self) -> List[UserRow]:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE vip_status='active'"
                )
                return await cursor.fetchall()

        except Exception:
            logger.exception("Get all active users error")
            raise

    async def is_user_active(self, telegram_id: int) -> bool:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    """
                    SELECT 1
                    FROM users
                    WHERE telegram_id=?
                    AND vip_status='active'
                    """,
                    (telegram_id,),
                )
                row = await cursor.fetchone()
                return row is not None

        except Exception:
            logger.exception("Is user active check error")
            raise

    async def update_invite_link(
        self,
        telegram_id: int,
        invite_link: Optional[str],
    ) -> None:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute(
                    """
                    UPDATE users
                    SET invite_link=?
                    WHERE telegram_id=?
                    """,
                    (invite_link, telegram_id),
                )
                await conn.commit()

        except Exception:
            logger.exception("Update invite link error")
            raise

    async def update_balance(
        self,
        telegram_id: int,
        balance: float,
        record_check: bool = True,
    ) -> None:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                if record_check:
                    await conn.execute(
                        """
                        UPDATE users
                        SET
                            balance=?,
                            last_check=datetime('now')
                        WHERE telegram_id=?
                        """,
                        (balance, telegram_id),
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE users
                        SET balance=?
                        WHERE telegram_id=?
                        """,
                        (balance, telegram_id),
                    )
                await conn.commit()

        except Exception:
            logger.exception("Update balance error")
            raise

    async def add_warning(self, telegram_id: int) -> None:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute(
                    """
                    UPDATE users
                    SET
                        warning_count=warning_count+1,
                        last_warning=datetime('now')
                    WHERE telegram_id=?
                    """,
                    (telegram_id,),
                )
                await conn.commit()

        except Exception:
            logger.exception("Add warning error")
            raise

    async def reset_warnings(self, telegram_id: int) -> None:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute(
                    """
                    UPDATE users
                    SET
                        warning_count=0,
                        last_warning=NULL
                    WHERE telegram_id=?
                    """,
                    (telegram_id,),
                )
                await conn.commit()

        except Exception:
            logger.exception("Reset warnings error")
            raise

    async def deactivate_user(self, telegram_id: int) -> None:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute(
                    """
                    UPDATE users
                    SET
                        vip_status='inactive',
                        last_check=datetime('now')
                    WHERE telegram_id=?
                    """,
                    (telegram_id,),
                )
                await conn.commit()

            logger.info("User deactivated: telegram_id=%s", telegram_id)

        except Exception:
            logger.exception("Deactivate user error")
            raise

    async def track_bot_user(
        self,
        telegram_id: int,
        username: Optional[str],
        first_name: Optional[str],
    ) -> None:
        """Remember users who interact with the bot for admin statistics."""
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute(
                    """
                    INSERT INTO bot_users(
                        telegram_id,
                        username,
                        first_name
                    )
                    VALUES(?, ?, ?)
                    ON CONFLICT(telegram_id) DO UPDATE SET
                        username=excluded.username,
                        first_name=excluded.first_name,
                        last_seen=datetime('now')
                    """,
                    (telegram_id, username, first_name),
                )
                await conn.commit()
        except Exception:
            logger.exception("Track bot user error")
            raise

    async def get_admin_stats(self) -> UserRow:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    """
                    SELECT
                        (
                            SELECT COUNT(*)
                            FROM (
                                SELECT telegram_id FROM bot_users
                                UNION
                                SELECT telegram_id FROM users
                            )
                        ) AS total_bot_users,
                        COUNT(*) AS total_vip_records,
                        SUM(CASE WHEN vip_status='active' THEN 1 ELSE 0 END)
                            AS active_vips,
                        SUM(CASE WHEN vip_status='inactive' THEN 1 ELSE 0 END)
                            AS inactive_vips,
                        COALESCE(SUM(
                            CASE WHEN vip_status='active' THEN balance ELSE 0 END
                        ), 0) AS active_balance_total,
                        COALESCE(SUM(warning_count), 0) AS total_warnings,
                        MAX(last_check) AS latest_check
                    FROM users
                    """
                )
                return await cursor.fetchone()
        except Exception:
            logger.exception("Get admin stats error")
            raise

    async def get_bot_user(
        self,
        telegram_id: int,
    ) -> Optional[UserRow]:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    """
                    SELECT *
                    FROM bot_users
                    WHERE telegram_id=?
                    """,
                    (telegram_id,),
                )
                return await cursor.fetchone()
        except Exception:
            logger.exception("Get bot user error")
            raise

    async def find_user(self, identifier: str) -> Optional[UserRow]:
        """Find a VIP record by Telegram ID or Yubit UID."""
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    """
                    SELECT *
                    FROM users
                    WHERE CAST(telegram_id AS TEXT)=?
                       OR yubit_uid=?
                    ORDER BY
                        CASE WHEN yubit_uid=? THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (identifier, identifier, identifier),
                )
                return await cursor.fetchone()
        except Exception:
            logger.exception("Find user error")
            raise

    async def get_broadcast_user_ids(self) -> List[int]:
        """Return every known user once, including historical VIP records."""
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    """
                    SELECT telegram_id FROM bot_users
                    UNION
                    SELECT telegram_id FROM users
                    ORDER BY telegram_id
                    """
                )
                rows = await cursor.fetchall()
                return [int(row["telegram_id"]) for row in rows]
        except Exception:
            logger.exception("Get broadcast recipients error")
            raise

    async def get_all_vip_users(self) -> List[UserRow]:
        """Return active and inactive VIP records for admin export."""
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    """
                    SELECT *
                    FROM users
                    ORDER BY
                        CASE WHEN vip_status='active' THEN 0 ELSE 1 END,
                        joined_at DESC,
                        telegram_id
                    """
                )
                return await cursor.fetchall()
        except Exception:
            logger.exception("Get all VIP users error")
            raise

    async def save_support_message(
        self,
        admin_chat_id: int,
        admin_message_id: int,
        user_telegram_id: int,
    ) -> None:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO support_messages(
                        admin_chat_id,
                        admin_message_id,
                        user_telegram_id
                    )
                    VALUES(?, ?, ?)
                    """,
                    (
                        admin_chat_id,
                        admin_message_id,
                        user_telegram_id,
                    ),
                )
                await conn.commit()
        except Exception:
            logger.exception("Save support message error")
            raise

    async def get_support_user(
        self,
        admin_chat_id: int,
        admin_message_id: int,
    ) -> Optional[int]:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    """
                    SELECT user_telegram_id
                    FROM support_messages
                    WHERE admin_chat_id=?
                      AND admin_message_id=?
                    """,
                    (admin_chat_id, admin_message_id),
                )
                row = await cursor.fetchone()
                if row is None:
                    return None
                return int(row["user_telegram_id"])
        except Exception:
            logger.exception("Get support user error")
            raise

    async def set_campaign(
        self,
        source_chat_id: int,
        source_message_id: int,
    ) -> None:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                await conn.execute(
                    """
                    INSERT INTO campaign(
                        id,
                        source_chat_id,
                        source_message_id
                    )
                    VALUES(1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        source_chat_id=excluded.source_chat_id,
                        source_message_id=excluded.source_message_id,
                        updated_at=datetime('now')
                    """,
                    (source_chat_id, source_message_id),
                )
                await conn.commit()
        except Exception:
            logger.exception("Set campaign error")
            raise

    async def get_campaign(self) -> Optional[UserRow]:
        try:
            async with self._connect() as conn:
                await self._prepare(conn)
                cursor = await conn.execute(
                    "SELECT * FROM campaign WHERE id=1"
                )
                return await cursor.fetchone()
        except Exception:
            logger.exception("Get campaign error")
            raise


db = Database()
