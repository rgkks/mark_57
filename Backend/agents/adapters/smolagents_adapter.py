"""smolagents adapter — verified working against Kilo.ai."""
from __future__ import annotations

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events


class SmolagentsAdapter(BaseAgent):
    id = "smolagents"
    name = "smolagents Code Agent"
    description = "Lightweight coding agent that writes and runs code."
    capabilities = ["code", "coding", "math", "computation", "data", "files"]
    framework = "smolagents"
    available = False

    def health_check(self) -> dict:
        try:
            import smolagents  # noqa: F401
            self.available = True
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": True, "status": "online"}
        except Exception as e:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "error": str(e)}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        events.log_agent(task_id or "", self.id, self.framework, "smolagents/code",
                         phase="start", task=task)
        try:
            from Backend.agents.llm import smolagents_model
            from smolagents import CodeAgent
            model = smolagents_model()
            agent = CodeAgent(
                tools=[],
                model=model,
                max_steps=8,
                additional_authorized_imports=[
                    "os", "sys", "shutil", "pathlib", "subprocess", "json",
                    "requests", "urllib", "urllib.request", "openai", "dotenv",
                    "random", "math", "time", "datetime",
                ],
            )
            result = agent.run(task)
            return self._success(str(result))
        except Exception as e:
            events.log_error(task_id or "", str(e), agent_id=self.id)
            return self._failed(str(e))


# Alias used by registry
Adapter = SmolagentsAdapter
