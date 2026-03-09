"""SQLite persistence for user profile, ideas, and sessions."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .models import AppIdea, UserInterest, SessionRecord


class IdeaStore:
    """SQLite-backed store for the idea generator."""

    def __init__(self, db_path: str = "data/ideagen.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS interests (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic      TEXT    NOT NULL,
                    weight     REAL    NOT NULL DEFAULT 0.5,
                    source     TEXT    NOT NULL DEFAULT 'inferred',
                    created_at TEXT    DEFAULT (datetime('now')),
                    updated_at TEXT    DEFAULT (datetime('now')),
                    UNIQUE(topic)
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    direction       TEXT    NOT NULL DEFAULT 'open',
                    ideas_generated INTEGER DEFAULT 0,
                    ideas_liked     INTEGER DEFAULT 0,
                    started_at      TEXT    DEFAULT (datetime('now')),
                    ended_at        TEXT
                );

                CREATE TABLE IF NOT EXISTS ideas (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    title          TEXT    NOT NULL,
                    one_liner      TEXT    NOT NULL DEFAULT '',
                    description    TEXT    NOT NULL,
                    category       TEXT    NOT NULL DEFAULT 'other',
                    market_angle   TEXT    NOT NULL DEFAULT '',
                    personal_angle TEXT    NOT NULL DEFAULT '',
                    target_users   TEXT    NOT NULL DEFAULT '',
                    monetization   TEXT    NOT NULL DEFAULT '',
                    complexity     TEXT    NOT NULL DEFAULT 'medium',
                    tags           TEXT    NOT NULL DEFAULT '[]',
                    reaction       TEXT,
                    notes          TEXT    NOT NULL DEFAULT '',
                    session_id     INTEGER REFERENCES sessions(id),
                    created_at     TEXT    DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS direction_history (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES sessions(id),
                    direction  TEXT    NOT NULL,
                    created_at TEXT    DEFAULT (datetime('now'))
                );
            """)

    # ── Interests ──

    def add_interest(self, topic: str, weight: float = 0.5, source: str = "inferred") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO interests (topic, weight, source)
                   VALUES (?, ?, ?)
                   ON CONFLICT(topic) DO UPDATE SET
                     weight = MAX(weight, excluded.weight),
                     source = excluded.source,
                     updated_at = datetime('now')""",
                (topic.lower().strip(), weight, source),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def boost_interest(self, topic: str, delta: float = 0.1) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE interests
                   SET weight = MIN(1.0, weight + ?), updated_at = datetime('now')
                   WHERE topic = ?""",
                (delta, topic.lower().strip()),
            )

    def decay_interest(self, topic: str, delta: float = 0.05) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE interests
                   SET weight = MAX(0.0, weight - ?), updated_at = datetime('now')
                   WHERE topic = ?""",
                (delta, topic.lower().strip()),
            )

    def get_interests(self, min_weight: float = 0.1, limit: int = 30) -> list[UserInterest]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, topic, weight, source, created_at, updated_at
                   FROM interests WHERE weight >= ? ORDER BY weight DESC LIMIT ?""",
                (min_weight, limit),
            ).fetchall()
        return [UserInterest(*r) for r in rows]

    def get_top_interests(self, n: int = 10) -> list[str]:
        return [i.topic for i in self.get_interests(limit=n)]

    # ── Sessions ──

    def start_session(self, direction: str = "open") -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (direction) VALUES (?)", (direction,)
            )
            return cur.lastrowid  # type: ignore[return-value]

    def end_session(self, session_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = datetime('now') WHERE id = ?",
                (session_id,),
            )

    def update_session_stats(self, session_id: int, generated: int, liked: int) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE sessions
                   SET ideas_generated = ?, ideas_liked = ?
                   WHERE id = ?""",
                (generated, liked, session_id),
            )

    def get_session(self, session_id: int) -> Optional[SessionRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, direction, ideas_generated, ideas_liked, started_at, ended_at "
                "FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return SessionRecord(*row) if row else None

    def get_recent_sessions(self, limit: int = 10) -> list[SessionRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, direction, ideas_generated, ideas_liked, started_at, ended_at "
                "FROM sessions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [SessionRecord(*r) for r in rows]

    # ── Ideas ──

    def save_idea(self, idea: AppIdea) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO ideas
                   (title, one_liner, description, category, market_angle,
                    personal_angle, target_users, monetization, complexity,
                    tags, reaction, notes, session_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    idea.title, idea.one_liner, idea.description, idea.category,
                    idea.market_angle, idea.personal_angle, idea.target_users,
                    idea.monetization, idea.complexity,
                    json.dumps(idea.tags), idea.reaction, idea.notes, idea.session_id,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def react_to_idea(self, idea_id: int, reaction: str, notes: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE ideas SET reaction = ?, notes = ? WHERE id = ?",
                (reaction, notes, idea_id),
            )

    def get_idea(self, idea_id: int) -> Optional[AppIdea]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        return self._row_to_idea(row) if row else None

    def get_saved_ideas(self) -> list[AppIdea]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE reaction = 'save' OR reaction = 'love' "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_idea(r) for r in rows]

    def get_session_ideas(self, session_id: int) -> list[AppIdea]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [self._row_to_idea(r) for r in rows]

    def get_reaction_history(self, limit: int = 50) -> list[AppIdea]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE reaction IS NOT NULL "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_idea(r) for r in rows]

    # ── Direction history ──

    def log_direction(self, session_id: int, direction: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO direction_history (session_id, direction) VALUES (?, ?)",
                (session_id, direction),
            )

    def get_direction_history(self, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT direction, created_at FROM direction_history "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"direction": r[0], "created_at": r[1]} for r in rows]

    # ── Helpers ──

    @staticmethod
    def _row_to_idea(row: tuple) -> AppIdea:
        return AppIdea(
            id=row[0], title=row[1], one_liner=row[2], description=row[3],
            category=row[4], market_angle=row[5], personal_angle=row[6],
            target_users=row[7], monetization=row[8], complexity=row[9],
            tags=json.loads(row[10]) if row[10] else [],
            reaction=row[11], notes=row[12], session_id=row[13], created_at=row[14],
        )
