"""Voting executor — polls for approved ideas and triggers the BuilderAgent."""

import asyncio
import logging
from typing import Optional

from .idea_pool import IdeaPool

log = logging.getLogger(__name__)


class VotingExecutor:
    """Watches for approved ideas and queues them for development."""

    def __init__(self, pool: IdeaPool, orchestrator=None, poll_secs: int = 3600):
        self.pool = pool
        self.orchestrator = orchestrator
        self.poll_secs = poll_secs
        self._running = False

    async def process_approved(self) -> list[dict]:
        """Find approved ideas and dispatch them to the builder agent."""
        with __import__("sqlite3").connect(str(self.pool.db_path)) as conn:
            rows = conn.execute(
                "SELECT * FROM ideas WHERE status='approved' ORDER BY votes DESC"
            ).fetchall()

        results = []
        for row in rows:
            idea = self.pool._to_dict(row)
            self.pool.set_status(idea["id"], "in_development")
            log.info("Sending idea #%d to builder: %s", idea["id"], idea["title"])

            if self.orchestrator:
                result = await self.orchestrator.dispatch(
                    {"type": "build", "idea": idea},
                    agent_name="builder",
                )
                if result.success:
                    self.pool.set_status(idea["id"], "deployed")
                else:
                    self.pool.set_status(idea["id"], "approved")  # retry next cycle
                    log.warning("Builder failed for #%d: %s", idea["id"], result.error)
            results.append(idea)
        return results

    async def start(self) -> None:
        self._running = True
        while self._running:
            await self.process_approved()
            await asyncio.sleep(self.poll_secs)

    def stop(self) -> None:
        self._running = False
