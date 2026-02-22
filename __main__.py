"""Entry point: python -m orchestration_box (or python __main__.py from repo root)."""

import asyncio
import logging
import sys

from agents.loader import load_agents
from core.budget import BudgetManager
from core.orchestrator import Orchestrator
from voting.idea_pool import IdeaPool
from voting.scheduler import VotingScheduler
from voting.executor import VotingExecutor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")


async def main() -> None:
    budget = BudgetManager()
    registry = load_agents()
    orchestrator = Orchestrator(registry, budget)
    pool = IdeaPool()
    scheduler = VotingScheduler(pool)
    executor = VotingExecutor(pool, orchestrator)

    log.info("Orchestration Box started. Agents: %s", [a["name"] for a in registry.summary()])
    log.info("Budget: %s", budget.summary())

    # Seed an example idea if pool is empty (remove after first run)
    if not pool.get_pending():
        pool.submit(
            title="Token-usage weekly digest",
            description="Weekly email/log summarising token spend vs revenue with trend.",
            submitted_by="system",
            category="maintenance",
            est_tokens_saved=500,
        )
        log.info("Seeded example idea into voting pool.")

    await asyncio.gather(
        scheduler.start(registry.all()),
        executor.start(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
