"""Task Classifier + Agent Router with graceful fallbacks.

Routing considers:
- task intent (keyword + optional LLM classification)
- specialist capabilities
- framework availability (from health check)
- tool availability
- failure history
- fallback chains
"""
from __future__ import annotations

import uuid

from Backend.agents import events
from Backend.agents.adapters import get_adapter_classes
from Backend.agents.health import run_health_check
from Backend.agents.specialists import SPECIALISTS, match_specialists
from Backend.agents.base import AgentResult


class AgentRegistry:
    """Holds instantiated adapters keyed by id, with availability from health."""

    def __init__(self, health: dict = None):
        self.classes = get_adapter_classes()
        self._health = health  # None => computed lazily on first availability query
        self.adapters = {}
        # Adapters instantiate lazily too; availability derived from health.
        self._adapters_loaded = False

    def _ensure_health(self):
        if self._health is None:
            self._health = run_health_check()
        return self._health

    def _ensure_adapters(self):
        if self._adapters_loaded:
            return
        health = self._ensure_health()
        for aid, cls in self.classes.items():
            try:
                inst = cls()
                inst.available = health.get(aid, {}).get("status") == "online"
                self.adapters[aid] = inst
            except Exception:
                self.adapters[aid] = None
        self._adapters_loaded = True

    def available_ids(self) -> list:
        health = self._ensure_health()
        return [aid for aid, h in health.items() if h.get("status") == "online"]

    def get(self, aid: str):
        self._ensure_adapters()
        return self.adapters.get(aid)

    def status(self):
        health = self._ensure_health()
        return {aid: h.get("status", "unknown") for aid, h in health.items()}


class Router:
    def __init__(self, registry: AgentRegistry = None, use_llm_classifier: bool = True):
        self.registry = registry or AgentRegistry()
        self.use_llm_classifier = use_llm_classifier
        self.failure_history = {}

    # ---- Intent classification ----------------------------------------------
    def _classify_intent(self, task: str) -> str:
        """Return a specialist name for the task (LLM-assisted classifier)."""
        if self.use_llm_classifier:
            try:
                from Backend.agents.llm import chat
                names = ", ".join(s.name for s in SPECIALISTS)
                prompt = (
                    f"Choose the single best specialist from this list for the user's request.\n"
                    f"Specialists: {names}\n"
                    f"Reply with ONLY the specialist name.\n"
                    f"Request: {task}"
                )
                answer = chat([{"role": "user", "content": prompt}], max_tokens=10, temperature=0.0)
                answer = answer.strip().lower().split()[0] if answer.strip() else ""
                for s in SPECIALISTS:
                    if s.name in answer:
                        return s.name
            except Exception:
                pass
        # Keyword fallback (no LLM / LLM failed)
        ranked = match_specialists(task)
        return ranked[0].name if ranked else "coder"

    # ---- Framework selection -------------------------------------------------
    def _pick_framework(self, specialist_name: str) -> str:
        """Choose the best available framework for a specialist with fallbacks."""
        spec = next((s for s in SPECIALISTS if s.name == specialist_name), None)
        available = set(self.registry.available_ids())
        if spec is None:
            return self._first_available(["smolagents", "crewai", "langgraph"], available)
        chain = [spec.preferred] + spec.fallbacks
        for fw in chain:
            if fw in available:
                return fw
        # fallback to any online framework
        for fw in ["smolagents", "crewai", "langgraph", "browser-use", "agent-framework"]:
            if fw in available:
                return fw
        return None

    def _first_available(self, candidates: list, available: set) -> str:
        for c in candidates:
            if c in available:
                return c
        return None

    # ---- Routing -------------------------------------------------------------
    def route(self, task: str) -> dict:
        """Return {specialist, framework, adapter_id} for a task."""
        specialist = self._classify_intent(task)
        framework = self._pick_framework(specialist)
        return {
            "specialist": specialist,
            "framework": framework,
            "adapter_id": framework,
        }

    # ---- Execution with fallback --------------------------------------------
    def run(self, task: str, context: dict = None) -> AgentResult:
        task_id = (context or {}).get("task_id") if context else uuid.uuid4().hex[:12]
        ctx = {**(context or {}), "task_id": task_id}
        events.log_task(task_id, task)
        routing = self.route(task)
        return self._execute_chain(task, routing["specialist"], ctx)

    def run_for_specialist(self, specialist: str, task: str, context: dict = None) -> AgentResult:
        """Run a task against a specific specialist (used by workflows)."""
        task_id = (context or {}).get("task_id") if context else uuid.uuid4().hex[:12]
        ctx = {**(context or {}), "task_id": task_id}
        return self._execute_chain(task, specialist, ctx)

    def run_parallel(self, tasks: list, context: dict = None) -> list:
        """Run independent tasks concurrently (threads). Safe: only for
        tasks that do NOT depend on each other."""
        import concurrent.futures
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(tasks) or 1)) as ex:
            futures = [ex.submit(self.run, t, context) for t in tasks]
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as e:
                    results.append(AgentResult(status="failed", agent_id="router",
                                               errors=[str(e)]))
        return results

    def _execute_chain(self, task: str, specialist: str, ctx: dict) -> AgentResult:
        """Run a task via a specialist's framework chain with fallback."""
        task_id = ctx.get("task_id")
        chosen_fw = self._pick_framework(specialist)

        if chosen_fw is None:
            events.log_error(task_id, "no available framework")
            return AgentResult(task_id=task_id, agent_id="router", status="failed",
                               errors=["No available agent framework"], output="")

        spec = next((s for s in SPECIALISTS if s.name == specialist), None)
        chain = []
        if spec:
            chain = [spec.preferred] + spec.fallbacks
        chain = [chosen_fw] + [f for f in chain if f != chosen_fw]
        available = set(self.registry.available_ids())
        chain = [f for f in chain if f in available]

        last_error = None
        for fw in chain:
            adapter = self.registry.get(fw)
            if adapter is None or not adapter.available:
                continue
            events.log_agent(task_id, adapter.id, adapter.framework, "kilo.ai",
                             phase="route", specialist=specialist)
            try:
                result = adapter.execute(task, ctx)
                result.task_id = task_id
                if result.status == "success":
                    events.log_result(task_id, "success", agent_id=adapter.id,
                                      framework=adapter.framework)
                    return result
                last_error = result.errors
                if fw != chain[-1]:
                    events.log_fallback(task_id, fw, chain[chain.index(fw) + 1],
                                        f"failed: {result.errors}")
            except Exception as e:
                last_error = [str(e)]
                if fw != chain[-1]:
                    events.log_fallback(task_id, fw, chain[chain.index(fw) + 1], str(e))

        events.log_result(task_id, "failed", reason=str(last_error))
        return AgentResult(task_id=task_id, agent_id="router", status="failed",
                           errors=last_error or ["all frameworks failed"], output="")
