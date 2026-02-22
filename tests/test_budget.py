"""Tests for BudgetManager."""

import pytest
from core.budget import BudgetManager


@pytest.fixture
def budget(tmp_path):
    return BudgetManager(db_path=str(tmp_path / "budget.db"), daily_limit=1000)


def test_initial_usage_zero(budget):
    assert budget.today_tokens() == 0


def test_record_and_query(budget):
    budget.record("agent_a", 300)
    budget.record("agent_b", 200)
    assert budget.today_tokens() == 500


def test_can_proceed(budget):
    budget.record("agent_a", 900)
    assert not budget.can_proceed(200)
    assert budget.can_proceed(50)


def test_revenue_expands_limit(budget):
    # $1 revenue → at $0.01/1k tokens, 60% reinvested over 30 days
    budget.record_revenue(1.0)
    extra = int(1.0 * 0.60 / 0.01 * 1000 / 30)
    assert budget.effective_limit() == 1000 + extra


def test_summary_keys(budget):
    s = budget.summary()
    assert {"today_tokens", "daily_limit", "remaining_today", "pct_used"} <= s.keys()
