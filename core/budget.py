"""Token budget manager — tracks usage and enforces daily limits."""

import os
import sqlite3
from pathlib import Path


class BudgetManager:
    def __init__(
        self,
        db_path: str = "data/budget.db",
        daily_limit: int | None = None,
    ):
        self.daily_limit = daily_limit or int(os.getenv("DAILY_TOKEN_LIMIT", "100000"))
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent     TEXT    NOT NULL,
                    tokens    INTEGER NOT NULL,
                    cost_usd  REAL    DEFAULT 0,
                    task_type TEXT    DEFAULT '',
                    ts        TEXT    DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS revenue (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount_usd REAL    NOT NULL,
                    source     TEXT    DEFAULT '',
                    ts         TEXT    DEFAULT (datetime('now'))
                )
            """)

    def record(self, agent: str, tokens: int, cost_usd: float = 0.0, task_type: str = "") -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO token_usage (agent, tokens, cost_usd, task_type) VALUES (?,?,?,?)",
                (agent, tokens, cost_usd, task_type),
            )

    def record_revenue(self, amount_usd: float, source: str = "") -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO revenue (amount_usd, source) VALUES (?,?)",
                (amount_usd, source),
            )

    def today_tokens(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens),0) FROM token_usage WHERE DATE(ts)=DATE('now')"
            ).fetchone()
            return row[0]

    def effective_limit(self) -> int:
        """Daily limit expanded by reinvested revenue (60% of total revenue / 30 days)."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT COALESCE(SUM(amount_usd),0) FROM revenue").fetchone()
            total_revenue = row[0]
        # Rough: $0.01 per 1000 haiku tokens; reinvest 60%
        extra_tokens = int(total_revenue * 0.60 / 0.01 * 1000 / 30)
        return self.daily_limit + extra_tokens

    def can_proceed(self, estimated_tokens: int = 500) -> bool:
        return self.today_tokens() + estimated_tokens <= self.effective_limit()

    def summary(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            today = conn.execute(
                "SELECT COALESCE(SUM(tokens),0), COALESCE(SUM(cost_usd),0) "
                "FROM token_usage WHERE DATE(ts)=DATE('now')"
            ).fetchone()
            total = conn.execute(
                "SELECT COALESCE(SUM(tokens),0), COALESCE(SUM(cost_usd),0) FROM token_usage"
            ).fetchone()
            revenue = conn.execute(
                "SELECT COALESCE(SUM(amount_usd),0) FROM revenue"
            ).fetchone()
        limit = self.effective_limit()
        return {
            "today_tokens": today[0],
            "today_cost_usd": round(today[1], 4),
            "total_tokens": total[0],
            "total_cost_usd": round(total[1], 4),
            "total_revenue_usd": round(revenue[0], 2),
            "daily_limit": limit,
            "remaining_today": max(0, limit - today[0]),
            "pct_used": round(today[0] / limit * 100, 1) if limit else 0,
        }
