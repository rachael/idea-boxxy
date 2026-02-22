"""Notifier — formats and dispatches notifications (stdout, webhook, email stub)."""

import time
import json
import logging
import os
from datetime import datetime

import httpx

from core.agent import BaseAgent, AgentConfig, TaskResult

log = logging.getLogger(__name__)

CHANNELS = {"stdout", "webhook", "log"}


class Notifier(BaseAgent):
    """Send notifications through configured channels.

    Task schema:
        {"type": "notify", "subject": str, "body": str, "channel": "stdout|webhook|log",
         "severity": "info|warning|critical"}
    """

    def __init__(self):
        super().__init__(AgentConfig(
            name="notifier",
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            tags=["notification", "alert"],
        ))
        self.webhook_url: str | None = os.getenv("NOTIFY_WEBHOOK_URL")

    async def run(self, task: dict) -> TaskResult:
        start = time.monotonic()
        subject = task.get("subject", "Orchestration Box Notification")
        body = task.get("body", "")
        channel = task.get("channel", "stdout")
        severity = task.get("severity", "info")

        if channel not in CHANNELS:
            channel = "stdout"

        payload = {
            "subject": subject,
            "body": body,
            "severity": severity,
            "ts": datetime.utcnow().isoformat(),
        }

        error = None
        if channel == "stdout":
            print(f"[{severity.upper()}] {subject}: {body}")
        elif channel == "log":
            getattr(log, severity if severity in ("info", "warning", "error") else "info")(
                "%s: %s", subject, body
            )
        elif channel == "webhook" and self.webhook_url:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(self.webhook_url, json=payload)
            except httpx.HTTPError as exc:
                error = str(exc)
        elif channel == "webhook":
            error = "NOTIFY_WEBHOOK_URL not set"

        return TaskResult(
            success=error is None,
            output=payload,
            tokens_used=0,  # no LLM call needed
            agent_name=self.name,
            duration_ms=(time.monotonic() - start) * 1000,
            error=error,
        )
