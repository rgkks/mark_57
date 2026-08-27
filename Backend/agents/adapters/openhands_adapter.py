"""OpenHands adapter (optional / heavy).

OpenHands runs via the ghcr.io/openhands/agent-server Docker image. This is a
placeholder so it can be installed later WITHOUT architectural changes. It does
not run in the core runtime by default.
"""
from __future__ import annotations

import shutil

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events

_AGENT_SERVER_IMAGE = "ghcr.io/openhands/agent-server:latest"


class OpenHandsAdapter(BaseAgent):
    id = "openhands"
    name = "OpenHands"
    description = "OpenHands autonomous coding agent (via agent-server Docker image)."
    capabilities = ["coding", "software", "autonomous", "repo", "docker"]
    framework = "openhands"
    available = False

    def health_check(self) -> dict:
        docker = shutil.which("docker")
        if not docker:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "note": "docker not found"}
        self.available = True
        return {"id": self.id, "name": self.name, "framework": self.framework,
                "available": True, "status": "online",
                "note": f"docker available; image: {_AGENT_SERVER_IMAGE}"}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        return self._failed(
            "OpenHands not wired into runtime yet; requires agent-server container",
            task_id=task_id,
        )


Adapter = OpenHandsAdapter
