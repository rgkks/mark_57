"""Mindcraft adapter — LLM Minecraft bot (Node.js + Mineflayer).

Mindcraft controls a Minecraft bot via Mineflayer. It can only execute when
a Minecraft Java world is running and opened to LAN on port 55916. The
health check reports honest availability: ONLINE only if node is installed
AND a Minecraft world is reachable on the configured port.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events

_MINDCRAFT_DIR = os.path.join(os.getcwd(), "Backend", "resources", "agent", "mindcraft")
_PROFILE = os.path.join(_MINDCRAFT_DIR, "jarvis.json")
_HOST = "127.0.0.1"
_PORT = 55916


def _port_reachable(host: str = _HOST, port: int = _PORT, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class MindcraftAdapter(BaseAgent):
    id = "mindcraft"
    name = "Mindcraft Minecraft Agent"
    description = "LLM-controlled Minecraft bot that plays and builds in a live Minecraft world."
    capabilities = ["minecraft", "game", "play", "build in minecraft", "minecraft bot"]
    framework = "mindcraft"
    available = False

    def _node_ok(self) -> bool:
        return shutil.which("node") is not None

    def health_check(self) -> dict:
        node = self._node_ok()
        installed = os.path.isdir(os.path.join(_MINDCRAFT_DIR, "node_modules"))
        world_up = _port_reachable()
        self.available = bool(node and installed and world_up)
        note = "ready" if self.available else (
            "missing node" if not node else
            "not installed" if not installed else
            "no Minecraft world on port %d" % _PORT
        )
        return {"id": self.id, "name": self.name, "framework": self.framework,
                "available": self.available, "status": "online" if self.available else "offline",
                "note": note}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        if not self.available:
            return self._failed("Mindcraft unavailable: needs a running Minecraft world "
                                "opened to LAN on port %d" % _PORT, task_id=task_id)
        events.log_agent(task_id or "", self.id, self.framework, "kilo.ai",
                         phase="start", task=task)
        try:
            env = {**os.environ, "MAX_MESSAGES": "2"}
            proc = subprocess.Popen(
                ["node", "main.js", "--profiles", _PROFILE],
                cwd=_MINDCRAFT_DIR, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            # Give the bot a bounded run; collect output for a short while.
            import time
            time.sleep(8)
            proc.terminate()
            out, _ = proc.communicate(timeout=5)
            summary = out.strip().splitlines()[-3:]
            return self._success(
                output=out[-1500:],
                summary=f"Mindcraft bot ran (task: {task}) | {' | '.join(summary)}",
                metadata={"exit_code": proc.returncode},
            )
        except Exception as e:
            events.log_error(task_id or "", str(e), agent_id=self.id)
            return self._failed(str(e), task_id=task_id)


Adapter = MindcraftAdapter