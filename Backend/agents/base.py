"""Common agent interface for the JARVIS multi-agent router.

Every framework adapter implements BaseAgent so the rest of JARVIS never
talks to framework-specific APIs directly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


class AgentStatus:
    """Lifecycle states every specialist can be in."""

    IDLE = "IDLE"
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"


@dataclass
class AgentResult:
    """Normalized result returned by every agent regardless of framework."""

    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    status: str = "success"  # success | failed | partial
    summary: str = ""          # short human-readable summary
    output: Any = ""
    artifacts: list = field(default_factory=list)
    sources: list = field(default_factory=list)  # source URLs / file paths
    errors: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def ok(self) -> bool:
        return self.status == "success"


class BaseAgent:
    """Abstract base for all agent adapters.

    Subclasses MUST set: id, name, description, capabilities, framework.
    Subclasses SHOULD implement: execute(), health_check().
    """

    id: str = "base"
    name: str = "Base Agent"
    description: str = ""
    capabilities: list = []
    framework: str = "unknown"
    available: bool = False

    def __init__(self, context: Optional[dict] = None):
        self.context = context or {}
        self.failure_history: list = []

    # ---- Required interface -------------------------------------------------
    def execute(self, task: str, context: Optional[dict] = None) -> AgentResult:
        """Run the task and return a normalized AgentResult."""
        raise NotImplementedError

    def health_check(self) -> dict:
        """Return a health report dict. Base default reports availability."""
        return {
            "id": self.id,
            "name": self.name,
            "framework": self.framework,
            "available": self.available,
            "status": "online" if self.available else "offline",
        }

    # ---- Helpers ------------------------------------------------------------
    def _result(
        self,
        status: str,
        output: Any = "",
        summary: str = "",
        sources: Optional[list] = None,
        artifacts: Optional[list] = None,
        errors: Optional[list] = None,
        metadata: Optional[dict] = None,
        task_id: Optional[str] = None,
    ) -> AgentResult:
        return AgentResult(
            task_id=task_id or uuid.uuid4().hex[:12],
            agent_id=self.id,
            status=status,
            summary=summary or (str(output)[:200] if output else ""),
            output=output,
            artifacts=artifacts or [],
            sources=sources or [],
            errors=errors or [],
            metadata=metadata or {"framework": self.framework},
        )

    def _success(self, output: Any = "", summary: str = "", sources: Optional[list] = None, **kw) -> AgentResult:
        self.failure_history = []
        return self._result("success", output=output, summary=summary, sources=sources, **kw)

    def _failed(self, error: str, **kw) -> AgentResult:
        self.failure_history.append(error)
        return self._result("failed", errors=[error], **kw)

    def _partial(self, output: Any = "", errors: Optional[list] = None, **kw) -> AgentResult:
        self.failure_history.extend(errors or [])
        return self._result("partial", output=output, errors=errors or [], **kw)

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id!r} available={self.available}>"