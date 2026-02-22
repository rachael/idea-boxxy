"""Main orchestrator — routes tasks to agents with budget awareness."""

import asyncio
import logging
from typing import Optional

from .agent import TaskResult
from .budget import BudgetManager
from .registry import AgentRegistry

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, registry: AgentRegistry, budget: BudgetManager):
        self.registry = registry
        self.budget = budget

    async def dispatch(self, task: dict, agent_name: Optional[str] = None) -> TaskResult:
        """Route a task to a named agent or auto-select by capability."""
        if not self.budget.can_proceed():
            log.warning("Daily token budget exhausted, blocking task: %s", task.get("type"))
            return TaskResult(
                success=False,
                output=None,
                tokens_used=0,
                agent_name="orchestrator",
                duration_ms=0,
                error="Daily token budget exhausted",
            )

        agent = None
        if agent_name:
            agent = self.registry.get(agent_name)

        if not agent:
            candidates = self.registry.find(task.get("type", ""))
            if candidates:
                agent = candidates[0]

        if not agent:
            return TaskResult(
                success=False,
                output=None,
                tokens_used=0,
                agent_name="orchestrator",
                duration_ms=0,
                error=f"No agent for task type '{task.get('type', '?')}'",
            )

        log.info("Dispatching %s → %s", task.get("type", "?"), agent.name)
        result = await agent.run(task)
        self.budget.record(
            agent=result.agent_name,
            tokens=result.tokens_used,
            task_type=task.get("type", ""),
        )
        return result

    async def broadcast(self, task: dict, capability: str) -> list[TaskResult]:
        """Run a task on every agent with the given capability (e.g. voting)."""
        agents = self.registry.find(capability)
        if not agents:
            return []
        return await asyncio.gather(*[a.run(task) for a in agents])
