"""Tests for ideagen store (persistence layer)."""

import tempfile
import os
import pytest

from ideagen.store import IdeaStore
from ideagen.models import AppIdea


@pytest.fixture
def store(tmp_path):
    return IdeaStore(db_path=str(tmp_path / "test_ideagen.db"))


class TestInterests:
    def test_add_and_retrieve(self, store):
        store.add_interest("python", weight=0.8, source="stated")
        interests = store.get_interests()
        assert len(interests) == 1
        assert interests[0].topic == "python"
        assert interests[0].weight == 0.8

    def test_upsert_keeps_higher_weight(self, store):
        store.add_interest("python", weight=0.3)
        store.add_interest("python", weight=0.9)
        interests = store.get_interests()
        assert len(interests) == 1
        assert interests[0].weight == 0.9

    def test_boost_and_decay(self, store):
        store.add_interest("rust", weight=0.5)
        store.boost_interest("rust", 0.2)
        interests = store.get_interests()
        assert interests[0].weight == pytest.approx(0.7)
        store.decay_interest("rust", 0.3)
        interests = store.get_interests()
        assert interests[0].weight == pytest.approx(0.4)

    def test_weight_clamped(self, store):
        store.add_interest("go", weight=0.95)
        store.boost_interest("go", 0.5)
        interests = store.get_interests()
        assert interests[0].weight == 1.0

    def test_top_interests(self, store):
        store.add_interest("a", weight=0.9)
        store.add_interest("b", weight=0.5)
        store.add_interest("c", weight=0.7)
        top = store.get_top_interests(n=2)
        assert top == ["a", "c"]

    def test_min_weight_filter(self, store):
        store.add_interest("strong", weight=0.8)
        store.add_interest("weak", weight=0.05)
        interests = store.get_interests(min_weight=0.1)
        assert len(interests) == 1
        assert interests[0].topic == "strong"


class TestSessions:
    def test_create_and_retrieve(self, store):
        sid = store.start_session("productivity apps")
        session = store.get_session(sid)
        assert session is not None
        assert session.direction == "productivity apps"
        assert session.ended_at is None

    def test_end_session(self, store):
        sid = store.start_session()
        store.end_session(sid)
        session = store.get_session(sid)
        assert session.ended_at is not None

    def test_update_stats(self, store):
        sid = store.start_session()
        store.update_session_stats(sid, generated=10, liked=3)
        session = store.get_session(sid)
        assert session.ideas_generated == 10
        assert session.ideas_liked == 3


class TestIdeas:
    def _make_idea(self, session_id=None):
        return AppIdea(
            id=0, title="Test App", one_liner="A test app",
            description="An app for testing",
            category="productivity", market_angle="Everyone needs it",
            personal_angle="You love testing",
            target_users="Developers", monetization="Freemium",
            complexity="small", tags=["test", "dev"],
            session_id=session_id,
        )

    def test_save_and_retrieve(self, store):
        idea = self._make_idea()
        idea_id = store.save_idea(idea)
        retrieved = store.get_idea(idea_id)
        assert retrieved is not None
        assert retrieved.title == "Test App"
        assert retrieved.tags == ["test", "dev"]

    def test_react(self, store):
        idea_id = store.save_idea(self._make_idea())
        store.react_to_idea(idea_id, "love", notes="This is great!")
        idea = store.get_idea(idea_id)
        assert idea.reaction == "love"
        assert idea.notes == "This is great!"

    def test_saved_ideas(self, store):
        id1 = store.save_idea(self._make_idea())
        id2 = store.save_idea(self._make_idea())
        id3 = store.save_idea(self._make_idea())
        store.react_to_idea(id1, "love")
        store.react_to_idea(id2, "dislike")
        store.react_to_idea(id3, "save")
        saved = store.get_saved_ideas()
        assert len(saved) == 2

    def test_session_ideas(self, store):
        sid = store.start_session()
        store.save_idea(self._make_idea(session_id=sid))
        store.save_idea(self._make_idea(session_id=sid))
        store.save_idea(self._make_idea(session_id=None))
        ideas = store.get_session_ideas(sid)
        assert len(ideas) == 2


class TestDirectionHistory:
    def test_log_and_retrieve(self, store):
        sid = store.start_session()
        store.log_direction(sid, "AI tools")
        store.log_direction(sid, "health apps")
        history = store.get_direction_history()
        assert len(history) == 2
        assert history[0]["direction"] == "health apps"  # most recent first
