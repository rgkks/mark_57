"""Microsoft Agent Framework adapter (best-effort).

Uses the official OpenAIChatClient pointed at the kilo.ai gateway.
If the framework or client fails, the adapter reports unavailable without
breaking the router.
"""
from __future__ import annotations

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events


class AgentFrameworkAdapter(BaseAgent):
    id = "agent-framework"
    name = "Microsoft Agent Framework"
    description = "Microsoft's agent framework for building chat and workflow agents."
    capabilities = ["chat", "agent", "workflow", "mcp", "tools"]
    framework = "agent-framework"
    available = False

    def health_check(self) -> dict:
        try:
            import agent_framework  # noqa: F401
            from agent_framework.openai import OpenAIChatClient  # noqa: F401
            self.available = True
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": True, "status": "online"}
        except Exception as e:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "error": str(e)}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        events.log_agent(task_id or "", self.id, self.framework, "agent-framework/kilo",
                         phase="start", task=task)
        try:
            import asyncio
            from agent_framework import Agent
            from agent_framework.openai import OpenAIChatClient
            from Backend.agents.llm import OPENAI_BASE, DUMMY_KEY, chat_model

            client = OpenAIChatClient(
                model=chat_model(),
                api_key=DUMMY_KEY,
                base_url=OPENAI_BASE,
            )
            agent = Agent(client=client, instructions="Answer concisely and correctly.")

            async def _run():
                response = await agent.run(messages=task)
                return response

            result = asyncio.run(_run())
            text = (
                getattr(result, "final_output", None)
                or getattr(result, "output", None)
                or (str(result))
            )
            return self._success(str(text))
        except Exception as e:
            events.log_error(task_id or "", str(e), agent_id=self.id)
            return self._failed(str(e))


Adapter = AgentFrameworkAdapter
