"""MaintenanceBot — checks system health, cleans up, reports stale state."""

import time
import sqlite3
from pathlib import Path
import anthropic

from core.agent import BaseAgent, AgentConfig, TaskResult

_SYSTEM = """\
You are a maintenance bot. Report system health concisely.
Check: disk usage, old log files, database sizes, stale jobs, budget status.
Output a short status report with any action items."""


class MaintenanceBot(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(
            name="maintenance_bot",
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system_prompt=_SYSTEM,
            tags=["maintenance", "health", "cleanup"],
        ))
        self._client = anthropic.Anthropic()

    async def run(self, task: dict) -> TaskResult:
        start = time.monotonic()
        health = self._collect_health()
        prompt = f"Health snapshot:\n{health}\n\nProvide status report and action items."
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=self.config.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return TaskResult(
            success=True,
            output=resp.content[0].text,
            tokens_used=resp.usage.input_tokens + resp.usage.output_tokens,
            agent_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def _collect_health(self) -> str:
        lines: list[str] = []
        data_dir = Path("data")
        if data_dir.exists():
            for db in data_dir.glob("*.db"):
                size_kb = db.stat().st_size // 1024
                lines.append(f"DB {db.name}: {size_kb} KB")
        log_dir = Path("logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            lines.append(f"Log files: {len(log_files)}")
        if not lines:
            lines.append("No data directory found yet.")
        return "\n".join(lines)

    async def evaluate_idea(self, idea: dict) -> tuple[int, str]:
        """Score idea 1-5 on maintenance/ops value."""
        import json
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f'Score 1-5 on maintenance value. JSON {{"score":N,"reason":"..."}}. '
                    f'Idea: {idea["title"]} — {idea["description"]}'
                ),
            }],
        )
        try:
            data = json.loads(resp.content[0].text)
            return int(data.get("score", 3)), data.get("reason", "")
        except (json.JSONDecodeError, ValueError):
            return 3, "parse error"
