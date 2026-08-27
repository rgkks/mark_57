"""open-browser-use adapter (optional / heavy).

open-browser-use is a local MCP browser driver. This placeholder lets it be
installed later without architectural changes. It does not run by default.
"""
from __future__ import annotations

import shutil

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events


class OpenBrowserUseAdapter(BaseAgent):
    id = "open-browser-use"
    name = "open-browser-use"
    description = "Local browser driver (MCP) for private browser automation."
    capabilities = ["browser", "web", "local", "mcp", "privacy"]
    framework = "open-browser-use"
    available = False

    def health_check(self) -> dict:
        obu = shutil.which("obu") or shutil.which("open-browser-use")
        if not obu:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "note": "obu binary not found"}
        self.available = True
        return {"id": self.id, "name": self.name, "framework": self.framework,
                "available": True, "status": "online", "note": f"obu at {obu}"}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        return self._failed(
            "open-browser-use not wired into runtime yet; requires obu + browser extension",
            task_id=task_id,
        )


Adapter = OpenBrowserUseAdapter
