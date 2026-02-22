"""Tests for VotingScheduler."""

import pytest
from unittest.mock import AsyncMock
from voting.idea_pool import IdeaPool
from voting.scheduler import VotingScheduler
from core.agent import BaseAgent, AgentConfig, TaskResult


class FakeAgent(BaseAgent):
    def __init__(self, name: str, score: int):
        super().__init__(AgentConfig(name=name, tags=["test"]))
        self._score = score

    async def run(self, task: dict) -> TaskResult:
        return TaskResult(True, None, 0, self.name, 0)

    async def evaluate_idea(self, idea: dict) -> tuple[int, str]:
        return self._score, "test vote"


@pytest.fixture
def pool(tmp_path):
    return IdeaPool(db_path=str(tmp_path / "ideas.db"))


@pytest.mark.asyncio
async def test_round_approves_high_score(pool):
    pool.submit("Great idea", "Revenue generator", "scout", "revenue", est_revenue_usd=50)
    agents = [FakeAgent("a", 5), FakeAgent("b", 4)]
    scheduler = VotingScheduler(pool, approval_avg=3.0)
    result = await scheduler.run_round(agents, round_id="test-1")
    assert result["voted"] == 1
    assert len(result["approved"]) == 1


@pytest.mark.asyncio
async def test_round_rejects_low_score(pool):
    pool.submit("Weak idea", "Not useful", "scout", "tool")
    agents = [FakeAgent("a", 1), FakeAgent("b", 2)]
    scheduler = VotingScheduler(pool, approval_avg=3.0)
    result = await scheduler.run_round(agents, round_id="test-2")
    assert result["voted"] == 1
    assert len(result["approved"]) == 0
