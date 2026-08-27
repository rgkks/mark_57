"""Cua adapter — computer-use agent (best-effort).

Cua is primarily a cloud/fleet computer-use SDK that needs a running OS
sandbox or credentials. Health check reports honest availability; if no
sandbox/fleet is available the adapter marks itself unavailable without
breaking the router.
"""
from __future__ import annotations

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events


class CuaAdapter(BaseAgent):
    id = "cua"
    name = "Cua Computer Agent"
    description = "Desktop/computer-use agent that controls a real OS environment."
    capabilities = ["desktop", "computer use", "gui", "mouse", "keyboard", "screenshots"]
    framework = "cua"
    available = False

    def health_check(self) -> dict:
        try:
            import cua  # noqa: F401
            # A real task requires a sandbox/fleet. Without it, cua is importable
            # but not usable, so we report unavailable.
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline",
                    "note": "importable but requires a compute sandbox/fleet to run"}
        except Exception as e:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "error": str(e)}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        if not self.available:
            return self._failed("Cua unavailable: requires a compute sandbox/fleet",
                                task_id=task_id)
        events.log_agent(task_id or "", self.id, self.framework, "cua",
                         phase="start", task=task)
        try:
            # Real execution path goes here once a sandbox is configured.
            raise NotImplementedError("Cua sandbox not configured")
        except Exception as e:
            events.log_error(task_id or "", str(e), agent_id=self.id)
            return self._failed(str(e))


Adapter = CuaAdapter
