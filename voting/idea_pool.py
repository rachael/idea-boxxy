"""Shared idea pool — agents submit tool/agent ideas, votes accumulate here."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


CATEGORIES = {"revenue", "tool", "agent", "maintenance", "security", "notification", "personal"}


@dataclass
class Idea:
    id: int
    title: str
    description: str
    submitted_by: str
    category: str
    est_tokens_saved: int
    est_revenue_usd: float
    votes: int
    status: str  # pending | approved | in_development | deployed | rejected
    created_at: str


class IdeaPool:
    """SQLite-backed shared pool for agent-generated ideas."""

    def __init__(self, db_path: str = "data/ideas.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ideas (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    title           TEXT    NOT NULL,
                    description     TEXT    NOT NULL,
                    submitted_by    TEXT    NOT NULL,
                    category        TEXT    NOT NULL,
                    est_tokens_saved INTEGER DEFAULT 0,
                    est_revenue_usd REAL    DEFAULT 0,
                    votes           INTEGER DEFAULT 0,
                    status          TEXT    DEFAULT 'pending',
                    created_at      TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    idea_id  INTEGER NOT NULL,
                    voter    TEXT    NOT NULL,
                    round_id TEXT    NOT NULL,
                    score    INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                    rationale TEXT   DEFAULT '',
                    voted_at TEXT    DEFAULT (datetime('now')),
                    UNIQUE(idea_id, voter, round_id)
                )
            """)

    def submit(
        self,
        title: str,
        description: str,
        submitted_by: str,
        category: str,
        est_tokens_saved: int = 0,
        est_revenue_usd: float = 0.0,
    ) -> int:
        """Submit a new idea; returns the new idea id."""
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category '{category}'. Valid: {CATEGORIES}")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO ideas
                   (title, description, submitted_by, category, est_tokens_saved, est_revenue_usd)
                   VALUES (?,?,?,?,?,?)""",
                (title, description, submitted_by, category, est_tokens_saved, est_revenue_usd),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def vote(self, idea_id: int, voter: str, round_id: str, score: int, rationale: str = "") -> bool:
        """Cast a vote. Returns False if duplicate (already voted this round)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO votes (idea_id, voter, round_id, score, rationale) VALUES (?,?,?,?,?)",
                    (idea_id, voter, round_id, score, rationale),
                )
                conn.execute(
                    "UPDATE ideas SET votes = votes + ? WHERE id = ?",
                    (score, idea_id),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_pending(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE status='pending' ORDER BY votes DESC"
            ).fetchall()
        return [self._to_dict(r) for r in rows]

    def get_top(self, limit: int = 5) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE status='pending' ORDER BY votes DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._to_dict(r) for r in rows]

    def set_status(self, idea_id: int, status: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE ideas SET status=? WHERE id=?", (status, idea_id))

    def get(self, idea_id: int) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
        return self._to_dict(row) if row else None

    @staticmethod
    def _to_dict(row: tuple) -> dict:
        keys = [
            "id", "title", "description", "submitted_by", "category",
            "est_tokens_saved", "est_revenue_usd", "votes", "status", "created_at",
        ]
        return dict(zip(keys, row))
