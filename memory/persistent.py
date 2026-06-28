import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional


class PersistentMemory:
    def __init__(self, db_path: str = "jarvis_memory.db") -> None:
        self._db_path = str(Path(db_path).resolve())
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT    NOT NULL DEFAULT 'general',
                key         TEXT    NOT NULL,
                value       TEXT    NOT NULL,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL,
                UNIQUE(category, key)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL,
                role        TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_category_key
                ON memories(category, key);
            CREATE INDEX IF NOT EXISTS idx_conversations_session
                ON conversations(session_id, timestamp);
        """)
        self._conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat(timespec="seconds")

    @staticmethod
    def _normalize(text: str) -> str:
        return unicodedata.normalize("NFKC", text)

    def remember(self, key: str, value: str, category: str = "general") -> None:
        key = self._normalize(key)
        value = self._normalize(value)
        now = self._now()
        self._conn.execute(
            """
            INSERT INTO memories (category, key, value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category, key) DO UPDATE SET
                value      = excluded.value,
                updated_at = excluded.updated_at
            """,
            (category, key, value, now, now),
        )
        self._conn.commit()

    def recall(self, key: str, category: str = "general") -> Optional[str]:
        key = self._normalize(key)
        row = self._conn.execute(
            "SELECT value FROM memories WHERE category = ? AND key = ?",
            (category, key),
        ).fetchone()
        return row["value"] if row else None

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query = self._normalize(query)
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """
            SELECT id, category, key, value, created_at, updated_at
            FROM memories
            WHERE key LIKE ? OR value LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def forget(self, key: str, category: str = "general") -> None:
        key = self._normalize(key)
        self._conn.execute(
            "DELETE FROM memories WHERE category = ? AND key = ?",
            (category, key),
        )
        self._conn.commit()

    def save_conversation_turn(
        self, session_id: str, role: str, content: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO conversations (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, self._normalize(content), self._now()),
        )
        self._conn.commit()

    def get_recent_conversations(
        self, session_id: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        if session_id is not None:
            rows = self._conn.execute(
                """
                SELECT id, session_id, role, content, timestamp
                FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT id, session_id, role, content, timestamp
                FROM conversations
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return list(reversed([dict(row) for row in rows]))

    def get_memory_summary(self) -> str:
        rows = self._conn.execute(
            "SELECT category, key, value FROM memories ORDER BY category, key"
        ).fetchall()
        if not rows:
            return ""
        lines: list[str] = ["[Memórias persistentes do Jarvis]"]
        current_category: Optional[str] = None
        for row in rows:
            if row["category"] != current_category:
                current_category = row["category"]
                lines.append(f"\n## {current_category}")
            lines.append(f"- {row['key']}: {row['value']}")
        return "\n".join(lines)

    def close(self) -> None:
        self._conn.close()
