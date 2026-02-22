"""Base protocol for all agents in the orchestration system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentConfig:
    name: str
    model: str = "claude-haiku-4-5-20251001"  # cheapest by default
    max_tokens: int = 1024
    system_prompt: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class TaskResult:
    success: bool
    output: Any
    tokens_used: int
    agent_name: str
    duration_ms: float
    error: Optional[str] = None


class BaseAgent(ABC):
    """Every agent must extend this class."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name

    @abstractmethod
    async def run(self, task: dict) -> TaskResult:
        """Execute the task and return a result."""

    @property
    def capabilities(self) -> list[str]:
        """Task types this agent can handle (from config tags)."""
        return self.config.tags

    async def evaluate_idea(self, idea: dict) -> tuple[int, str]:
        """Score an idea 1-5. Override for custom voting logic."""
        return 3, "default neutral vote"
