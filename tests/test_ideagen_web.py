"""Tests for ideagen web API."""

import json
import pytest
from unittest.mock import patch, MagicMock

from ideagen.web.app import create_app


@pytest.fixture
def client(tmp_path):
    with patch("ideagen.engine.anthropic.Anthropic"):
        app = create_app(db_path=str(tmp_path / "test.db"))
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


class TestBasicRoutes:
    def test_index_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Idea Boxxy" in resp.data

    def test_start_session(self, client):
        resp = client.post("/api/session", json={})
        data = resp.get_json()
        assert "session_id" in data
        assert data["session_id"] > 0

    def test_end_session(self, client):
        client.post("/api/session", json={})
        resp = client.delete("/api/session")
        data = resp.get_json()
        assert data["ended"] is not None

    def test_interests_empty(self, client):
        resp = client.get("/api/interests")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_saved_empty(self, client):
        resp = client.get("/api/saved")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_profile_empty(self, client):
        resp = client.get("/api/profile")
        data = resp.get_json()
        assert "interests" in data
        assert "directions" in data
        assert "sessions" in data


class TestGenerate:
    def test_generate_returns_ideas(self, client):
        ideas_json = json.dumps([{
            "title": "TestApp",
            "one_liner": "A test app",
            "description": "Testing",
            "category": "productivity",
            "market_angle": "Everyone",
            "personal_angle": "You",
            "target_users": "Devs",
            "monetization": "SaaS",
            "complexity": "small",
            "tags": ["test"],
        }])

        # Patch the engine's client at module level
        with patch("ideagen.engine.IdeaEngine.generate_ideas") as mock_gen:
            from ideagen.models import AppIdea
            mock_gen.return_value = [AppIdea(
                id=1, title="TestApp", one_liner="A test app",
                description="Testing", category="productivity",
                market_angle="Everyone", personal_angle="You",
                target_users="Devs", monetization="SaaS",
                complexity="small", tags=["test"],
            )]
            resp = client.post("/api/generate", json={"count": 1})
            data = resp.get_json()
            assert len(data) == 1
            assert data[0]["title"] == "TestApp"


class TestReact:
    def test_react_missing_fields(self, client):
        resp = client.post("/api/react", json={})
        assert resp.status_code == 400

    def test_react_idea_not_found(self, client):
        resp = client.post("/api/react", json={"idea_id": 999, "reaction": "love"})
        assert resp.status_code == 404


class TestDirections:
    def test_directions(self, client):
        with patch("ideagen.engine.IdeaEngine.suggest_directions") as mock_dirs:
            mock_dirs.return_value = ["AI tools", "Health apps"]
            resp = client.get("/api/directions")
            data = resp.get_json()
            assert len(data) == 2
