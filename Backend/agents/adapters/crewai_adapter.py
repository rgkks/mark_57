"""CrewAI adapter — verified working against Kilo.ai."""
from __future__ import annotations

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events


class CrewAIAdapter(BaseAgent):
    id = "crewai"
    name = "CrewAI Orchestrator"
    description = "Role-based multi-agent orchestration for complex tasks."
    capabilities = ["orchestration", "multi-agent", "complex", "planning", "research"]
    framework = "crewai"
    available = False

    def health_check(self) -> dict:
        try:
            from crewai import Agent, Task, Crew, LLM  # noqa: F401
            self.available = True
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": True, "status": "online"}
        except Exception as e:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "error": str(e)}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        events.log_agent(task_id or "", self.id, self.framework, "crewai/LLM",
                         phase="start", task=task)
        try:
            from Backend.agents.llm import crewai_llm
            from crewai import Agent, Task, Crew
            llm = crewai_llm()
            worker = Agent(
                role="worker",
                goal="complete the requested task accurately and concisely",
                backstory="You are a capable autonomous assistant.",
                llm=llm,
                allow_delegation=False,
            )
            task_obj = Task(description=task, expected_output="a clear final answer", agent=worker)
            crew = Crew(agents=[worker], tasks=[task_obj], verbose=False)
            result = crew.kickoff()
            return self._success(str(result))
        except Exception as e:
            events.log_error(task_id or "", str(e), agent_id=self.id)
            return self._failed(str(e))


Adapter = CrewAIAdapter
