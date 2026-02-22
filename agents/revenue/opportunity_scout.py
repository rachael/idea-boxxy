"""OpportunityScout — identifies revenue opportunities and evaluates ideas."""

import json
import time
import anthropic

from core.agent import BaseAgent, AgentConfig, TaskResult

_SYSTEM = """\
You identify specific, actionable revenue opportunities for a small AI-powered SaaS.
Focus on: API microservices, automation tools, niche data products, one-time scripts.
Be brief. Return JSON when asked. Realistic revenue estimates only."""


class OpportunityScout(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(
            name="opportunity_scout",
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system_prompt=_SYSTEM,
            tags=["revenue", "ideation", "opportunity"],
        ))
        self._client = anthropic.Anthropic()

    async def run(self, task: dict) -> TaskResult:
        context = task.get("context", "AI orchestration system")
        start = time.monotonic()
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=[{
                "role": "user",
                "content": (
                    f"List 3 revenue opportunities for: {context}. "
                    "For each: name, description, effort (S/M/L), monthly revenue estimate."
                ),
            }],
        )
        return TaskResult(
            success=True,
            output=resp.content[0].text,
            tokens_used=resp.usage.input_tokens + resp.usage.output_tokens,
            agent_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def evaluate_idea(self, idea: dict) -> tuple[int, str]:
        """Score idea 1-5 on revenue potential."""
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f'Score this idea 1-5 on revenue potential. '
                    f'Reply with JSON {{"score":N,"reason":"..."}}. '
                    f'Idea: {idea["title"]} — {idea["description"]}'
                ),
            }],
        )
        try:
            data = json.loads(resp.content[0].text)
            return int(data.get("score", 3)), data.get("reason", "")
        except (json.JSONDecodeError, ValueError):
            return 3, "parse error"
