"""Tests for ideagen engine (idea generation, interest inference)."""

import json
import pytest
from unittest.mock import MagicMock, patch

from ideagen.engine import IdeaEngine
from ideagen.store import IdeaStore
from ideagen.models import AppIdea


@pytest.fixture
def store(tmp_path):
    return IdeaStore(db_path=str(tmp_path / "test.db"))


@pytest.fixture
def engine(store):
    with patch("ideagen.engine.anthropic.Anthropic"):
        eng = IdeaEngine(store)
        yield eng


def _mock_response(text, input_tokens=100, output_tokens=200):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    return resp


class TestParseIdeas:
    def test_parse_valid_json(self, engine):
        text = json.dumps([{
            "title": "TestApp",
            "one_liner": "A test",
            "description": "Testing",
            "category": "productivity",
            "market_angle": "Everyone",
            "personal_angle": "You",
            "target_users": "Devs",
            "monetization": "SaaS",
            "complexity": "small",
            "tags": ["test"],
        }])
        ideas = engine._parse_ideas(text, session_id=None)
        assert len(ideas) == 1
        assert ideas[0].title == "TestApp"

    def test_parse_json_with_markdown_fences(self, engine):
        text = '```json\n[{"title":"App","one_liner":"x","description":"y"}]\n```'
        ideas = engine._parse_ideas(text, session_id=1)
        assert len(ideas) == 1
        assert ideas[0].session_id == 1

    def test_parse_json_embedded_in_text(self, engine):
        text = 'Here are the ideas:\n[{"title":"App","description":"y"}]\nDone!'
        ideas = engine._parse_ideas(text, session_id=None)
        assert len(ideas) == 1

    def test_parse_invalid_json(self, engine):
        ideas = engine._parse_ideas("not json at all", session_id=None)
        assert ideas == []


class TestGenerateIdeas:
    def test_generates_and_saves(self, engine, store):
        ideas_json = json.dumps([{
            "title": "FocusFlow",
            "one_liner": "Deep work timer with AI insights",
            "description": "A productivity app",
            "category": "productivity",
            "market_angle": "Remote workers need focus",
            "personal_angle": "You value efficiency",
            "target_users": "Knowledge workers",
            "monetization": "Freemium",
            "complexity": "small",
            "tags": ["productivity", "ai", "timer"],
        }])
        engine._client.messages.create.return_value = _mock_response(ideas_json)

        sid = store.start_session()
        ideas = engine.generate_ideas(count=1, session_id=sid)
        assert len(ideas) == 1
        assert ideas[0].title == "FocusFlow"
        assert ideas[0].id > 0  # was saved to DB

        # Verify persisted
        saved = store.get_session_ideas(sid)
        assert len(saved) == 1

    def test_direction_included_in_prompt(self, engine):
        engine._client.messages.create.return_value = _mock_response("[]")
        engine.generate_ideas(direction="health apps")
        call_args = engine._client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "health apps" in prompt


class TestProcessReaction:
    def test_love_boosts_interests(self, engine, store):
        idea = AppIdea(
            id=0, title="Test", one_liner="x", description="y",
            category="productivity", market_angle="", personal_angle="",
            target_users="", monetization="", complexity="small",
            tags=["python", "automation"],
        )
        idea.id = store.save_idea(idea)
        engine.process_reaction(idea, "love")

        interests = store.get_interests()
        topics = {i.topic for i in interests}
        assert "python" in topics
        assert "automation" in topics
        assert "productivity" in topics

    def test_dislike_decays_interests(self, engine, store):
        store.add_interest("boring_topic", weight=0.8)
        idea = AppIdea(
            id=0, title="Boring", one_liner="x", description="y",
            category="other", market_angle="", personal_angle="",
            target_users="", monetization="", complexity="small",
            tags=["boring_topic"],
        )
        idea.id = store.save_idea(idea)
        engine.process_reaction(idea, "dislike")

        interests = store.get_interests()
        boring = [i for i in interests if i.topic == "boring_topic"]
        assert boring[0].weight < 0.8


class TestInferInterests:
    def test_infer_from_reactions(self, engine, store):
        # Save some ideas with reactions
        for title in ["CodeHelper", "AutoDeploy"]:
            idea = AppIdea(
                id=0, title=title, one_liner="x", description="y",
                category="developer_tools", market_angle="", personal_angle="",
                target_users="", monetization="", complexity="small",
                tags=["dev"],
            )
            iid = store.save_idea(idea)
            store.react_to_idea(iid, "love")

        inferred = json.dumps([
            {"topic": "developer experience", "weight": 0.8, "reasoning": "test"},
        ])
        engine._client.messages.create.return_value = _mock_response(inferred)

        result = engine.infer_interests()
        assert len(result) == 1
        assert result[0]["topic"] == "developer experience"

        # Should be persisted
        interests = store.get_interests()
        topics = {i.topic for i in interests}
        assert "developer experience" in topics


class TestSuggestDirections:
    def test_returns_directions(self, engine):
        directions = json.dumps([
            "AI coding assistants",
            "Health tracking for developers",
            "Micro-SaaS ideas",
            "Creative writing tools",
            "Unusual IoT projects",
        ])
        engine._client.messages.create.return_value = _mock_response(directions)
        result = engine.suggest_directions()
        assert len(result) == 5

    def test_fallback_on_parse_error(self, engine):
        engine._client.messages.create.return_value = _mock_response("not json")
        result = engine.suggest_directions()
        assert len(result) == 5  # fallback defaults
