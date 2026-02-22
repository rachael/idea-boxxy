"""Central registry — agents self-register and are discoverable by capability."""

from typing import Optional, Type
from .agent import BaseAgent, AgentConfig


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def find(self, capability: str) -> list[BaseAgent]:
        """Return all agents that handle a given capability tag."""
        return [a for a in self._agents.values() if capability in a.capabilities]

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def summary(self) -> list[dict]:
        return [
            {"name": a.name, "model": a.config.model, "capabilities": a.capabilities}
            for a in self._agents.values()
        ]
