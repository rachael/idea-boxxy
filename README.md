# Orchestration Box

A self-sustaining multi-agent orchestration system. Agents handle personal tasks, app
creation, project management, security, maintenance, notifications, and revenue generation.
The system pays for its own token usage through revenue-generating agents.

## Design Principles

- **Token-minimal**: every agent defaults to the cheapest model that can do the job
- **Self-sustaining**: revenue agents offset operational token costs
- **Self-extending**: agents propose and vote on new tools; winners get built automatically
- **Security-first**: credential handling, secret scanning, and audit logging baked in

## Architecture

```
orchestration-box/
├── core/           # Base classes, registry, orchestrator, budget manager
├── agents/         # Implementations: pm, revenue, security, maintenance, notification, builder
├── voting/         # Idea pool, periodic voting rounds, auto-development of winners
├── config/         # settings.yaml, agents.yaml
└── tests/
```

## Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable, deployed state |
| `dev` | Integration — PRs merge here first |
| `feature/*` | New system capabilities |
| `agent/*` | Individual agent development |
| `fix/*` | Bug fixes |

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-ant-...
python -m core.orchestrator
```

## Token Budget

Set `DAILY_TOKEN_LIMIT` env var (default 100,000). The budget manager blocks execution
when the daily limit is reached and logs all usage to `data/budget.db`.

## Voting System

Every 7 days a voting round runs. Any agent can submit ideas to the shared pool at any
time. During a round, eligible agents score each pending idea 1–5. Ideas averaging ≥ 3
are approved and queued for the `BuilderAgent` to scaffold automatically.

## Revenue Loop

`OpportunityScout` identifies revenue opportunities weekly. `RevenueTracker` records
income. 60% of revenue is reinvested as additional daily token budget so the system
becomes increasingly self-funded over time.
