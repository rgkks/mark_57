"""JARVIS specialist workflows.

Composable multi-step workflows that chain specialists. Each step delegates
to the same router + adapters — no separate heavyweight LLM per agent.
"""
from __future__ import annotations

import os

from Backend.agents.base import AgentResult
from Backend.agents import events


def run_steps(router, steps: list, task: str, context: dict = None) -> list:
    """Run a chain of specialist steps in order. Returns list of results."""
    results = []
    for spec in steps:
        events.emit({"type": "workflow", "task": task, "step": spec, "status": "RUNNING"})
        routing = router.route(task)
        res = router.run_for_specialist(spec, task, context)
        results.append({"specialist": spec, "result": res})
        if res.status == "failed":
            break  # stop chain on hard failure
    return results


def coding_workflow(router, task: str, context: dict = None) -> AgentResult:
    """Planner -> Coder -> Tester -> Verifier"""
    events.emit({"type": "workflow", "name": "coding", "status": "start", "task": task})
    # Inspect project first (file agent), then code, then test, then verify.
    steps = ["planner", "coder", "tester", "verifier"]
    results = run_steps(router, steps, task, context)
    return _compose(results, task)


def debugging_loop(router, task: str, context: dict = None, max_retries: int = 3) -> AgentResult:
    """Error -> Analyze -> Fix -> Test -> Verify, with retry cap."""
    events.emit({"type": "workflow", "name": "debugging", "status": "start", "task": task})
    attempt = 0
    last = None
    while attempt < max_retries:
        attempt += 1
        steps = ["planner", "debugger", "coder", "tester"]
        results = run_steps(router, steps, task, context)
        last = results[-1]["result"] if results else None
        if last and last.status == "success":
            # verify
            v = router.run_for_specialist("verifier", task, context)
            if v.status == "success":
                return v
        events.emit({"type": "workflow", "name": "debugging", "attempt": attempt,
                     "status": "RETRYING"})
    # exhausted retries -> honest failure
    return AgentResult(
        status="failed",
        agent_id="workflow",
        summary=f"Debugging exhausted after {max_retries} attempts",
        errors=[last.errors if last else "no diagnosis"],
        metadata={"workflow": "debugging_loop", "attempts": attempt},
    )


def research_workflow(router, task: str, context: dict = None) -> AgentResult:
    """Researcher -> Web Search -> Source collection -> Summarizer -> Verifier"""
    events.emit({"type": "workflow", "name": "research", "status": "start", "task": task})
    steps = ["researcher", "web_search", "summarizer", "verifier"]
    results = run_steps(router, steps, task, context)
    return _compose(results, task)


def _compose(results: list, task: str) -> AgentResult:
    ok = [r for r in results if r["result"].status == "success"]
    failed = [r for r in results if r["result"].status == "failed"]
    sources = []
    for r in results:
        sources.extend(r["result"].sources or [])
    summary = "; ".join(r["result"].summary for r in results if r["result"].summary)
    status = "failed" if failed and not ok else ("partial" if failed else "success")
    return AgentResult(
        agent_id="workflow",
        status=status,
        summary=summary or f"Workflow completed for: {task}",
        output=[r["result"].to_dict() for r in results],
        artifacts=[r["result"].artifacts for r in results if r["result"].artifacts],
        sources=sources,
        errors=[r["result"].errors for r in failed],
        metadata={"workflow_steps": [r["specialist"] for r in results],
                  "completed": len(ok), "failed": len(failed)},
    )