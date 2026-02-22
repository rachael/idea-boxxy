"""Periodic voting rounds — agents score pending ideas, top ideas get approved."""

import asyncio
import logging
import uuid
from datetime import datetime

from .idea_pool import IdeaPool
from core.agent import BaseAgent

log = logging.getLogger(__name__)


class VotingScheduler:
    """Runs voting rounds on a configurable cadence."""

    def __init__(self, pool: IdeaPool, interval_days: int = 7, approval_avg: float = 3.0):
        self.pool = pool
        self.interval_days = interval_days
        self.approval_avg = approval_avg
        self._running = False

    def new_round_id(self) -> str:
        week = datetime.now().strftime("%Y-W%W")
        return f"{week}-{uuid.uuid4().hex[:6]}"

    async def run_round(self, agents: list[BaseAgent], round_id: str | None = None) -> dict:
        """Have each agent vote on all pending ideas. Approve winners."""
        round_id = round_id or self.new_round_id()
        ideas = self.pool.get_pending()

        if not ideas:
            log.info("Voting round %s: no pending ideas", round_id)
            return {"round_id": round_id, "voted": 0, "approved": []}

        log.info("Voting round %s: %d ideas, %d voters", round_id, len(ideas), len(agents))

        for agent in agents:
            for idea in ideas:
                score, rationale = await agent.evaluate_idea(idea)
                self.pool.vote(idea["id"], agent.name, round_id, score, rationale)

        # Approve ideas where average score >= threshold
        approved = []
        for idea in ideas:
            with __import__("sqlite3").connect(str(self.pool.db_path)) as conn:
                row = conn.execute(
                    "SELECT AVG(score) FROM votes WHERE idea_id=? AND round_id=?",
                    (idea["id"], round_id),
                ).fetchone()
            avg = row[0] or 0
            if avg >= self.approval_avg:
                self.pool.set_status(idea["id"], "approved")
                approved.append({"id": idea["id"], "title": idea["title"], "avg_score": round(avg, 2)})
                log.info("Idea #%d approved (avg %.1f): %s", idea["id"], avg, idea["title"])

        return {"round_id": round_id, "voted": len(ideas), "approved": approved}

    async def start(self, agents: list[BaseAgent]) -> None:
        """Run voting rounds forever on the configured interval."""
        self._running = True
        while self._running:
            await self.run_round(agents)
            await asyncio.sleep(self.interval_days * 86400)

    def stop(self) -> None:
        self._running = False
