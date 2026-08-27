"""Live agent status tracking for GUI integration.

Thread-safe registry of specialist lifecycle states, plus a snapshot the GUI
can poll (Frontend/Files/AgentStatus.json).
"""
from __future__ import annotations

import json
import os
import threading
import time

from Backend.agents.base import AgentStatus

_LOCK = threading.RLock()
_STATES = {}          # specialist_name -> state
_ACTIVE_TASK = None
_STATUS_FILE = os.path.join(os.getcwd(), "Frontend", "Files", "AgentStatus.json")


def _now():
    return time.strftime("%H:%M:%S")


def set_task(task: str):
    global _ACTIVE_TASK
    with _LOCK:
        _ACTIVE_TASK = task


def get_task():
    with _LOCK:
        return _ACTIVE_TASK


def set_state(specialist: str, state: str, agent_id: str = None):
    with _LOCK:
        _STATES[specialist] = {
            "specialist": specialist,
            "state": state,
            "agent_id": agent_id,
            "updated": _now(),
        }
        _flush()


def event(line: str, specialist: str = None):
    """Record an event line for the GUI event stream."""
    with _LOCK:
        entry = {"time": _now(), "event": line, "specialist": specialist}
        events_log.append(entry)
        if len(events_log) > 100:
            del events_log[: len(events_log) - 100]
        _flush()


events_log = []


def snapshot() -> dict:
    with _LOCK:
        return {
            "active_task": _ACTIVE_TASK,
            "agents": list(_STATES.values()),
            "events": list(events_log),
            "system": _system_snapshot(),
        }


def _system_snapshot() -> dict:
    try:
        from Backend.agents.tools.linux_tools import cpu_ram, disk_usage, network_status, uptime
        return {
            "cpu_ram": cpu_ram(),
            "disk": disk_usage(),
            "network": network_status(),
            "uptime": uptime(),
        }
    except Exception:
        return {}


def _flush():
    try:
        with open(_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot(), f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# convenience helpers matching specialist names
def running(specialist: str, agent_id: str = None):
    set_state(specialist, AgentStatus.RUNNING, agent_id)


def waiting(specialist: str, agent_id: str = None):
    set_state(specialist, AgentStatus.WAITING, agent_id)


def completed(specialist: str, agent_id: str = None):
    set_state(specialist, AgentStatus.COMPLETED, agent_id)


def failed(specialist: str, agent_id: str = None):
    set_state(specialist, AgentStatus.FAILED, agent_id)