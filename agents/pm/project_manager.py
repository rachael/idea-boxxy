"""ProjectManager — breaks down goals into tasks, tracks progress."""

import time
import anthropic

from core.agent import BaseAgent, AgentConfig, TaskResult

_SYSTEM = """\
You are a concise project manager for a small AI orchestration system.
Break goals into concrete tasks. Identify blockers. Suggest priorities.
Output plain text or markdown. No fluff."""


class ProjectManager(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(
            name="project_manager",
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system_prompt=_SYSTEM,
            tags=["pm", "planning", "task_breakdown"],
        ))
        self._client = anthropic.Anthropic()

    async def run(self, task: dict) -> TaskResult:
        goal = task.get("goal", task.get("content", ""))
        context = task.get("context", "")
        start = time.monotonic()
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=[{
                "role": "user",
                "content": f"Goal: {goal}\nContext: {context}\n\nCreate a task breakdown.",
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
        """Score idea 1-5 on feasibility and strategic value."""
        import json
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f'Score 1-5 on feasibility+value. JSON {{"score":N,"reason":"..."}}. '
                    f'Idea: {idea["title"]} — {idea["description"]}'
                ),
            }],
        )
        try:
            data = json.loads(resp.content[0].text)
            return int(data.get("score", 3)), data.get("reason", "")
        except (json.JSONDecodeError, ValueError):
            return 3, "parse error"
