"""JARVIS multi-agent system.

Unified abstraction so the rest of JARVIS doesn't care which framework is used.

Public API:
    from Backend.agents import router, health
    hc = health.health_report()
    result = router.run("task")   # returns AgentResult
"""
from __future__ import annotations

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents.router import Router, AgentRegistry
from Backend.agents.health import run_health_check, health_report
from Backend.agents import events, status, workflows

_default_router = None


def get_router() -> Router:
    """Return a shared router instance (lazily created)."""
    global _default_router
    if _default_router is None:
        _default_router = Router()
    return _default_router


def run(task: str, context: dict = None) -> AgentResult:
    """Route and run a task through the multi-agent system."""
    return get_router().run(task, context)


__all__ = [
    "BaseAgent", "AgentResult", "Router", "AgentRegistry",
    "run_health_check", "health_report", "events", "run", "get_router",
]
