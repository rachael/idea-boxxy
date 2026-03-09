"""Tests for ideagen CLI (smoke tests and flow logic)."""

import pytest
from unittest.mock import patch, MagicMock

from ideagen.cli import IdeaCLI, REACTION_MAP


@pytest.fixture
def cli(tmp_path):
    with patch("ideagen.engine.anthropic.Anthropic"):
        c = IdeaCLI(db_path=str(tmp_path / "test.db"))
        yield c


class TestCLIConstruction:
    def test_initializes(self, cli):
        assert cli.store is not None
        assert cli.engine is not None
        assert cli.session_id is None
        assert cli._ideas_generated == 0

    def test_session_lifecycle(self, cli):
        cli.session_id = cli.store.start_session("test")
        cli._ideas_generated = 5
        cli._ideas_liked = 2
        cli._end_session()

        session = cli.store.get_session(cli.session_id)
        assert session.ideas_generated == 5
        assert session.ideas_liked == 2
        assert session.ended_at is not None


class TestReactionMap:
    def test_all_reactions_mapped(self):
        assert "1" in REACTION_MAP  # love
        assert "2" in REACTION_MAP  # like
        assert "3" in REACTION_MAP  # meh
        assert "4" in REACTION_MAP  # dislike
        assert "s" in REACTION_MAP  # save
        assert "e" in REACTION_MAP  # explore

    def test_reaction_values(self):
        assert REACTION_MAP["1"].value == "love"
        assert REACTION_MAP["s"].value == "save"
        assert REACTION_MAP["e"].value == "explore"
