"""LangGraph adapter — verified working against Kilo.ai."""
from __future__ import annotations

from typing import TypedDict

from Backend.agents.base import BaseAgent, AgentResult
from Backend.agents import events


class LangGraphAdapter(BaseAgent):
    id = "langgraph"
    name = "LangGraph Workflow"
    description = "Stateful multi-step workflows and planning graphs."
    capabilities = ["workflow", "stateful", "planning", "multi-step", "graph"]
    framework = "langgraph"
    available = False

    def health_check(self) -> dict:
        try:
            from langgraph.graph import StateGraph, START, END  # noqa: F401
            self.available = True
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": True, "status": "online"}
        except Exception as e:
            self.available = False
            return {"id": self.id, "name": self.name, "framework": self.framework,
                    "available": False, "status": "offline", "error": str(e)}

    def execute(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else None
        events.log_agent(task_id or "", self.id, self.framework, "langgraph/llm",
                         phase="start", task=task)
        try:
            from langgraph.graph import StateGraph, START, END
            from Backend.agents.llm import openai_client, chat_model

            class State(TypedDict):
                query: str
                result: str

            client = openai_client()

            def think(state):
                r = client.chat.completions.create(
                    model=chat_model(),
                    messages=[{"role": "user", "content": state["query"]}],
                    max_tokens=512,
                )
                return {"result": r.choices[0].message.content}

            g = StateGraph(State)
            g.add_node("think", think)
            g.add_edge(START, "think")
            g.add_edge("think", END)
            out = g.compile().invoke({"query": task, "result": ""})
            return self._success(out["result"])
        except Exception as e:
            events.log_error(task_id or "", str(e), agent_id=self.id)
            return self._failed(str(e))


Adapter = LangGraphAdapter
