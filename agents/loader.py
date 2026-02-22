"""Dynamic agent loader — reads agents.yaml and instantiates registered agents."""

import importlib
import logging
from pathlib import Path

import yaml

from core.registry import AgentRegistry

log = logging.getLogger(__name__)


def load_agents(config_path: str = "config/agents.yaml") -> AgentRegistry:
    """Instantiate all enabled agents from config and return a populated registry."""
    registry = AgentRegistry()
    cfg = yaml.safe_load(Path(config_path).read_text())

    for spec in cfg.get("agents", []):
        if not spec.get("enabled", True):
            continue
        name = spec["name"]
        type_path = spec["type"]  # e.g. "revenue.opportunity_scout.OpportunityScout"
        parts = type_path.rsplit(".", 1)
        if len(parts) != 2:
            log.warning("Skipping %s: invalid type path %s", name, type_path)
            continue
        module_path, class_name = parts
        try:
            mod = importlib.import_module(f"agents.{module_path}")
            cls = getattr(mod, class_name)
            agent = cls()
            registry.register(agent)
            log.info("Loaded agent: %s (%s)", name, type_path)
        except Exception as exc:
            log.error("Failed to load agent %s: %s", name, exc)

    return registry
