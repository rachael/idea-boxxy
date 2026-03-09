"""Flask API backend for the idea generator web UI."""

import json
import logging
from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

from ..engine import IdeaEngine
from ..store import IdeaStore

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path: str = "data/ideagen.db") -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR))
    store = IdeaStore(db_path=db_path)
    engine = IdeaEngine(store)

    # Track active session per app instance (simple single-user setup)
    state = {"session_id": None}

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/api/session", methods=["POST"])
    def start_session():
        direction = request.json.get("direction", "open") if request.json else "open"
        state["session_id"] = store.start_session(direction)
        return jsonify({"session_id": state["session_id"]})

    @app.route("/api/session", methods=["DELETE"])
    def end_session():
        if state["session_id"]:
            store.end_session(state["session_id"])
            sid = state["session_id"]
            state["session_id"] = None
            return jsonify({"ended": sid})
        return jsonify({"ended": None})

    @app.route("/api/generate", methods=["POST"])
    def generate():
        data = request.json or {}
        direction = data.get("direction")
        count = min(data.get("count", 3), 5)
        avoid = data.get("avoid", [])

        ideas = engine.generate_ideas(
            count=count,
            direction=direction,
            session_id=state["session_id"],
            avoid_similar_to=avoid,
        )
        return jsonify([_idea_to_dict(i) for i in ideas])

    @app.route("/api/react", methods=["POST"])
    def react():
        data = request.json or {}
        idea_id = data.get("idea_id")
        reaction = data.get("reaction")
        notes = data.get("notes", "")

        if not idea_id or not reaction:
            return jsonify({"error": "idea_id and reaction required"}), 400

        idea = store.get_idea(idea_id)
        if not idea:
            return jsonify({"error": "idea not found"}), 404

        engine.process_reaction(idea, reaction)
        if notes:
            store.react_to_idea(idea_id, reaction, notes)

        return jsonify({"ok": True})

    @app.route("/api/explore/<int:idea_id>")
    def explore(idea_id):
        idea = store.get_idea(idea_id)
        if not idea:
            return jsonify({"error": "idea not found"}), 404
        details = engine.explore_idea(idea)
        return jsonify(details)

    @app.route("/api/directions")
    def directions():
        dirs = engine.suggest_directions()
        return jsonify(dirs)

    @app.route("/api/interests")
    def interests():
        items = store.get_interests(min_weight=0.05, limit=20)
        return jsonify([
            {"topic": i.topic, "weight": i.weight, "source": i.source}
            for i in items
        ])

    @app.route("/api/infer-interests", methods=["POST"])
    def infer_interests():
        result = engine.infer_interests()
        return jsonify(result)

    @app.route("/api/saved")
    def saved():
        ideas = store.get_saved_ideas()
        return jsonify([_idea_to_dict(i) for i in ideas])

    @app.route("/api/profile")
    def profile():
        interests_list = store.get_interests(min_weight=0.05, limit=20)
        directions_list = store.get_direction_history(limit=10)
        sessions = store.get_recent_sessions(limit=5)
        return jsonify({
            "interests": [
                {"topic": i.topic, "weight": i.weight, "source": i.source}
                for i in interests_list
            ],
            "directions": directions_list,
            "sessions": [
                {
                    "id": s.id, "direction": s.direction,
                    "ideas_generated": s.ideas_generated,
                    "ideas_liked": s.ideas_liked,
                    "started_at": s.started_at,
                }
                for s in sessions
            ],
        })

    return app


def _idea_to_dict(idea) -> dict:
    return {
        "id": idea.id,
        "title": idea.title,
        "one_liner": idea.one_liner,
        "description": idea.description,
        "category": idea.category,
        "market_angle": idea.market_angle,
        "personal_angle": idea.personal_angle,
        "target_users": idea.target_users,
        "monetization": idea.monetization,
        "complexity": idea.complexity,
        "tags": idea.tags,
        "reaction": idea.reaction,
        "created_at": idea.created_at,
    }
