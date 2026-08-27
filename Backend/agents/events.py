"""Observability: structured event stream for the JARVIS agent system.

The GUI can later subscribe to events to display agent activity live.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Optional

_EVENTS: list = []
_LOCK = threading.Lock()
_MAX_EVENTS = 500
_EVENT_LOG = os.path.join(os.getcwd(), "Frontend", "Files", "AgentEvents.json")


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def emit(event: dict) -> None:
    """Record an event. Safe to call from any thread."""
    entry = {
        "id": uuid.uuid4().hex[:12],
        "ts": _now(),
        **event,
    }
    with _LOCK:
        _EVENTS.append(entry)
        if len(_EVENTS) > _MAX_EVENTS:
            del _EVENTS[: len(_EVENTS) - _MAX_EVENTS]
        try:
            with open(_EVENT_LOG, "w", encoding="utf-8") as f:
                json.dump(_EVENTS, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def log_task(task_id: str, task: str, **fields) -> None:
    emit({"type": "task", "task_id": task_id, "task": task, **fields})


def log_agent(task_id: str, agent_id: str, framework: str, model: str, **fields) -> None:
    emit({
        "type": "agent",
        "task_id": task_id,
        "agent_id": agent_id,
        "framework": framework,
        "model": model,
        **fields,
    })


def log_result(task_id: str, status: str, **fields) -> None:
    emit({"type": "result", "task_id": task_id, "status": status, **fields})


def log_fallback(task_id: str, from_agent: str, to_agent: str, reason: str) -> None:
    emit({
        "type": "fallback",
        "task_id": task_id,
        "from": from_agent,
        "to": to_agent,
        "reason": reason,
    })


def log_error(task_id: str, message: str, **fields) -> None:
    emit({"type": "error", "task_id": task_id, "message": message, **fields})


def recent(limit: int = 50) -> list:
    with _LOCK:
        return list(_EVENTS[-limit:])


def stream():
    """Return a snapshot of all recorded events (for GUI polling)."""
    with _LOCK:
        return list(_EVENTS)
