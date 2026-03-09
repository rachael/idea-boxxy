"""Idea generation engine — uses Claude to generate app ideas and learn interests."""

import json
import logging
from typing import Optional

import anthropic

from .models import AppIdea, IdeaCategory
from .store import IdeaStore

log = logging.getLogger(__name__)

_IDEA_SYSTEM = """\
You are an expert app idea generator and product strategist. You generate creative,
specific, actionable app ideas that balance market demand with personal relevance.

Rules:
- Ideas must be specific and concrete, not vague ("AI-powered X" without details)
- Each idea needs a clear value proposition
- Consider feasibility for a solo developer or small team
- Mix ambitious and practical ideas
- Be creative — combine unexpected domains
- Always return valid JSON"""

_INTEREST_SYSTEM = """\
You are a perceptive interest profiler. Given a user's reactions to app ideas,
you infer their deeper interests, skills, and preferences. You look for patterns
beyond the obvious — if someone likes productivity tools, maybe they value
efficiency; if they like creative tools, maybe they enjoy making things.

Return valid JSON only."""


class IdeaEngine:
    """Generates app ideas using Claude, learns from user reactions."""

    def __init__(self, store: IdeaStore, model: str = "claude-haiku-4-5-20251001"):
        self.store = store
        self.model = model
        self._client = anthropic.Anthropic()

    def generate_ideas(
        self,
        count: int = 3,
        direction: Optional[str] = None,
        session_id: Optional[int] = None,
        avoid_similar_to: Optional[list[str]] = None,
    ) -> list[AppIdea]:
        """Generate app ideas, optionally steered by a direction."""
        interests = self.store.get_top_interests(n=15)
        recent_reactions = self._summarize_reactions()
        previously_generated = avoid_similar_to or []

        prompt = self._build_generation_prompt(
            count=count,
            direction=direction,
            interests=interests,
            reaction_summary=recent_reactions,
            avoid=previously_generated,
        )

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=_IDEA_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        ideas = self._parse_ideas(resp.content[0].text, session_id)
        for idea in ideas:
            idea.id = self.store.save_idea(idea)

        log.info(
            "Generated %d ideas (direction=%s, tokens=%d)",
            len(ideas), direction or "open",
            resp.usage.input_tokens + resp.usage.output_tokens,
        )
        return ideas

    def explore_idea(self, idea: AppIdea) -> dict:
        """Deep-dive into a specific idea — returns expanded details."""
        prompt = f"""Expand on this app idea with much more detail:

Title: {idea.title}
One-liner: {idea.one_liner}
Description: {idea.description}
Category: {idea.category}

Provide a detailed JSON response with:
{{
  "expanded_description": "2-3 paragraph detailed description",
  "key_features": ["list of 5-8 core features"],
  "tech_stack": "recommended technologies",
  "mvp_scope": "what a minimum viable product would look like",
  "differentiators": "what makes this unique vs existing solutions",
  "challenges": ["potential technical/business challenges"],
  "similar_apps": ["existing apps in this space, if any"],
  "revenue_potential": "realistic revenue analysis"
}}"""

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_IDEA_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            return json.loads(resp.content[0].text)
        except json.JSONDecodeError:
            return {"expanded_description": resp.content[0].text}

    def infer_interests(self) -> list[dict]:
        """Analyze reaction history and infer user interests."""
        history = self.store.get_reaction_history(limit=30)
        if not history:
            return []

        liked = [i for i in history if i.reaction in ("love", "like", "save", "explore")]
        disliked = [i for i in history if i.reaction in ("dislike", "meh")]

        if not liked and not disliked:
            return []

        liked_summary = "\n".join(
            f"- [{i.reaction}] {i.title}: {i.one_liner} (tags: {', '.join(i.tags)})"
            for i in liked[:15]
        )
        disliked_summary = "\n".join(
            f"- [{i.reaction}] {i.title}: {i.one_liner} (tags: {', '.join(i.tags)})"
            for i in disliked[:10]
        )

        prompt = f"""Based on these reactions to app ideas, infer the user's interests,
skills, and preferences. Look for deeper patterns.

LIKED/SAVED ideas:
{liked_summary or "(none yet)"}

DISLIKED/MEH ideas:
{disliked_summary or "(none yet)"}

Return a JSON array of inferred interests:
[
  {{"topic": "interest name", "weight": 0.0-1.0, "reasoning": "why you think this"}}
]

Include 3-8 interests. Weight reflects confidence (0.3 = weak signal, 0.9 = very clear).
Focus on underlying patterns, not just surface categories."""

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=_INTEREST_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            interests = json.loads(resp.content[0].text)
            for interest in interests:
                self.store.add_interest(
                    topic=interest["topic"],
                    weight=interest["weight"],
                    source="inferred",
                )
            log.info("Inferred %d interests from reaction history", len(interests))
            return interests
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Failed to parse inferred interests: %s", e)
            return []

    def suggest_directions(self) -> list[str]:
        """Suggest brainstorming directions based on interests and trends."""
        interests = self.store.get_top_interests(n=10)
        past_directions = self.store.get_direction_history(limit=10)

        prompt = f"""Suggest 5 interesting brainstorming directions for app ideas.

User interests: {', '.join(interests) if interests else 'unknown (new user)'}
Previous directions explored: {', '.join(d['direction'] for d in past_directions) if past_directions else 'none'}

Mix these types:
1. Directions based on their interests
2. Trending/timely directions they might not have considered
3. Creative cross-domain combinations
4. A wildcard / unexpected direction

Return a JSON array of strings, each being a concise direction (3-8 words):
["direction 1", "direction 2", ...]"""

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=256,
            system=_IDEA_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            return json.loads(resp.content[0].text)
        except json.JSONDecodeError:
            return [
                "Productivity tools for developers",
                "AI-assisted creative tools",
                "Personal finance automation",
                "Health & wellness tracking",
                "Niche community platforms",
            ]

    def process_reaction(self, idea: AppIdea, reaction: str) -> None:
        """Process a user reaction — update interests based on signal."""
        self.store.react_to_idea(idea.id, reaction)

        # Boost/decay interests based on the idea's tags and category
        if reaction in ("love", "save", "explore"):
            for tag in idea.tags:
                self.store.add_interest(tag, weight=0.6, source="reaction")
            self.store.add_interest(idea.category, weight=0.5, source="reaction")
        elif reaction == "like":
            for tag in idea.tags:
                self.store.add_interest(tag, weight=0.4, source="reaction")
        elif reaction == "dislike":
            for tag in idea.tags:
                self.store.decay_interest(tag, delta=0.1)
        # "meh" = no signal, don't update

    # ── Internal helpers ──

    def _build_generation_prompt(
        self,
        count: int,
        direction: Optional[str],
        interests: list[str],
        reaction_summary: str,
        avoid: list[str],
    ) -> str:
        parts = [f"Generate {count} app ideas.\n"]

        if direction:
            parts.append(f"DIRECTION: Focus on: {direction}\n")

        if interests:
            parts.append(f"User interests: {', '.join(interests)}\n")

        if reaction_summary:
            parts.append(f"Recent reaction patterns:\n{reaction_summary}\n")

        if avoid:
            parts.append(
                f"AVOID ideas similar to these already-generated ones: "
                f"{', '.join(avoid[:10])}\n"
            )

        parts.append("""
For each idea, consider:
- Market demand: What real problem does this solve? Who would pay for it?
- Personal relevance: Why would this interest the user specifically?
- Feasibility: Can a small team build an MVP?

Return a JSON array:
[
  {
    "title": "App Name",
    "one_liner": "One sentence pitch",
    "description": "2-3 sentence description",
    "category": "one of: productivity, developer_tools, ai_ml, health_fitness, finance, education, social, entertainment, creative_tools, data_analytics, automation, communication, ecommerce, sustainability, hardware_iot, other",
    "market_angle": "Why people would want this",
    "personal_angle": "Why this fits the user's interests",
    "target_users": "Who would use this",
    "monetization": "How to make money",
    "complexity": "small / medium / large",
    "tags": ["tag1", "tag2", "tag3"]
  }
]""")

        return "\n".join(parts)

    def _summarize_reactions(self) -> str:
        history = self.store.get_reaction_history(limit=20)
        if not history:
            return ""

        lines = []
        for idea in history[:10]:
            lines.append(f"[{idea.reaction}] {idea.title} ({idea.category})")
        return "\n".join(lines)

    def _parse_ideas(self, text: str, session_id: Optional[int]) -> list[AppIdea]:
        """Parse Claude's JSON response into AppIdea objects."""
        # Try to extract JSON from the response (might have markdown fences)
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON array in the text
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                log.warning("Could not parse ideas from response")
                return []

        ideas = []
        for item in data:
            ideas.append(AppIdea(
                id=0,
                title=item.get("title", "Untitled"),
                one_liner=item.get("one_liner", ""),
                description=item.get("description", ""),
                category=item.get("category", "other"),
                market_angle=item.get("market_angle", ""),
                personal_angle=item.get("personal_angle", ""),
                target_users=item.get("target_users", ""),
                monetization=item.get("monetization", ""),
                complexity=item.get("complexity", "medium"),
                tags=item.get("tags", []),
                session_id=session_id,
            ))
        return ideas
