"""Tests for IdeaPool."""

import pytest
from voting.idea_pool import IdeaPool


@pytest.fixture
def pool(tmp_path):
    return IdeaPool(db_path=str(tmp_path / "ideas.db"))


def test_submit_and_retrieve(pool):
    idea_id = pool.submit("Test idea", "A description", "agent_x", "tool")
    assert idea_id == 1
    pending = pool.get_pending()
    assert len(pending) == 1
    assert pending[0]["title"] == "Test idea"


def test_vote(pool):
    idea_id = pool.submit("Idea A", "Desc", "agent_x", "revenue")
    ok = pool.vote(idea_id, "voter_1", "round-1", 4, "great")
    assert ok
    duplicate = pool.vote(idea_id, "voter_1", "round-1", 5, "again")
    assert not duplicate


def test_set_status(pool):
    idea_id = pool.submit("Idea B", "Desc", "agent_y", "security")
    pool.set_status(idea_id, "approved")
    assert pool.get(idea_id)["status"] == "approved"
    assert pool.get_pending() == []


def test_invalid_category(pool):
    with pytest.raises(ValueError):
        pool.submit("Bad", "Desc", "agent", "unknown_category")
