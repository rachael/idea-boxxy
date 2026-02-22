"""SecurityAuditor — scans for secrets, audits configs, flags issues."""

import re
import time
import anthropic
from pathlib import Path

from core.agent import BaseAgent, AgentConfig, TaskResult

_SYSTEM = """\
You are a security auditor for a Python agent system. Be terse and precise.
Flag: hardcoded secrets, insecure configs, missing input validation, OWASP top 10 issues.
Output: severity (CRITICAL/HIGH/MEDIUM/LOW) + one-line description + file:line if known."""

# Regex patterns for common secret leaks
_SECRET_PATTERNS = [
    (r'sk-ant-[A-Za-z0-9\-_]{20,}', "Anthropic API key"),
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']', "Hardcoded password"),
    (r'(?i)(secret|token|api_?key)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret/token"),
    (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----', "Private key"),
]


class SecurityAuditor(BaseAgent):
    def __init__(self):
        super().__init__(AgentConfig(
            name="security_auditor",
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system_prompt=_SYSTEM,
            tags=["security", "audit"],
        ))
        self._client = anthropic.Anthropic()

    async def run(self, task: dict) -> TaskResult:
        target = task.get("path", ".")
        start = time.monotonic()

        # Fast local scan for secrets before calling the model
        local_findings = self._scan_secrets(target)

        prompt = task.get("prompt", f"Audit the agent system at {target} for security issues.")
        if local_findings:
            prompt += f"\n\nLocal scan findings:\n" + "\n".join(local_findings)

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

    def _scan_secrets(self, root: str) -> list[str]:
        findings: list[str] = []
        for path in Path(root).rglob("*.py"):
            if ".venv" in str(path) or "build" in str(path):
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            for pattern, label in _SECRET_PATTERNS:
                if re.search(pattern, text):
                    findings.append(f"CRITICAL: {label} detected in {path}")
        return findings

    async def evaluate_idea(self, idea: dict) -> tuple[int, str]:
        """Score idea 1-5 on security impact / risk reduction."""
        import json
        resp = self._client.messages.create(
            model=self.config.model,
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": (
                    f'Score 1-5 on security benefit. JSON {{"score":N,"reason":"..."}}. '
                    f'Idea: {idea["title"]} — {idea["description"]}'
                ),
            }],
        )
        try:
            data = json.loads(resp.content[0].text)
            return int(data.get("score", 3)), data.get("reason", "")
        except (json.JSONDecodeError, ValueError):
            return 3, "parse error"
