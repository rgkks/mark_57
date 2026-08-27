"""browser-use adapter — verified constructing against Kilo.ai via ChatOpenRouter."""
from __future__ import annotations

import os

from dotenv import dotenv_values

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events


def _env_bool(name: str, default: bool) -> bool:
    raw = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "jarvis.env")).get(name, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class BrowserUseAdapter(BaseAgent):
    id = "browser-use"
    name = "browser-use Agent"
    description = "Drives a real browser to complete web tasks."
    capabilities = ["browser", "web", "web automation", "forms", "navigation"]
    framework = "browser-use"
    available = False

    def health_check(self) -> dict:
        try:
            import browser_use  # noqa: F401
            from browser_use.llm.openrouter.chat import ChatOpenRouter  # noqa: F401
            from browser_use.browser.session import BrowserSession  # noqa: F401
            self.available = True
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": True, "status": "online"}
        except Exception as e:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "error": str(e)}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        events.log_agent(task_id or "", self.id, self.framework, "browser-use/ChatOpenRouter",
                         phase="start", task=task)
        try:
            import asyncio
            from browser_use import Agent as BrowserAgent
            from browser_use.llm.openrouter.chat import ChatOpenRouter
            from Backend.agents.llm import DUMMY_KEY, LITELLM_BASE, chat_model

            llm = ChatOpenRouter(
                model=chat_model(),
                api_key=DUMMY_KEY,
                base_url=LITELLM_BASE,
            )
            # The free kilo.ai chat model has no image input, so run the agent
            # visionless (text/HTML-based actions) unless browse-use_vision=True.
            agent = BrowserAgent(
                task=task,
                llm=llm,
                use_vision=_env_bool("browse-use_vision", False),
            )

            async def _run():
                history = await agent.run(max_steps=10)
                return history.final_result() if hasattr(history, "final_result") else str(history)

            final = asyncio.run(_run())
            return self._success(str(final))
        except Exception as e:
            events.log_error(task_id or "", str(e), agent_id=self.id)
            return self._failed(str(e))


Adapter = BrowserUseAdapter
