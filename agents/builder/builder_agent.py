"""BuilderAgent — scaffolds new agents/tools from approved voting ideas."""

import json
import time
import textwrap
from pathlib import Path
import anthropic

from core.agent import BaseAgent, AgentConfig, TaskResult

_SYSTEM = """\
You generate minimal, production-ready Python agent code for an orchestration system.
Agents extend core.agent.BaseAgent and implement async run(task) -> TaskResult.
Use claude-haiku-4-5-20251001 by default. Keep it token-efficient.
Return ONLY a JSON object:
{
  "filename": "agents/<family>/<snake_name>.py",
  "code": "<full python source>",
  "description": "<one line>"
}"""


class BuilderAgent(BaseAgent):
    """Scaffolds a new agent from a voting idea."""

    def __init__(self):
        super().__init__(AgentConfig(
            name="builder",
            model="claude-sonnet-4-6",   # needs more reasoning for code gen
            max_tokens=2048,
            system_prompt=_SYSTEM,
            tags=["build", "scaffold", "codegen"],
        ))
        self._client = anthropic.Anthropic()

    async def run(self, task: dict) -> TaskResult:
        idea = task.get("idea", {})
        start = time.monotonic()

        prompt = (
            f"Build an agent for this approved idea:\n"
            f"Title: {idea.get('title', '')}\n"
            f"Description: {idea.get('description', '')}\n"
            f"Category: {idea.get('category', '')}\n"
            f"Est. revenue: ${idea.get('est_revenue_usd', 0)}/mo\n"
            f"Est. tokens saved: {idea.get('est_tokens_saved', 0)}/day\n\n"
            f"Generate the agent code."
        )

        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = resp.content[0].text
        error = None
        output = None

        try:
            data = json.loads(raw)
            filename = data.get("filename", "")
            code = data.get("code", "")
            if filename and code:
                path = Path(filename)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(code)
                output = {"filename": str(path), "description": data.get("description", "")}
            else:
                error = "Builder returned incomplete JSON"
                output = raw
        except json.JSONDecodeError:
            error = "Builder response was not valid JSON"
            output = raw

        return TaskResult(
            success=error is None,
            output=output,
            tokens_used=resp.usage.input_tokens + resp.usage.output_tokens,
            agent_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
            error=error,
        )
