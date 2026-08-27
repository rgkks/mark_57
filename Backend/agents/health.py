"""Startup health check for all agent adapters.

Runs dependency/import checks and reports an honest status per adapter.
"""
from __future__ import annotations

import concurrent.futures

from Backend.agents.adapters import get_adapter_classes
from Backend.agents.specialists import SPECIALISTS


def run_health_check(timeout: int = 30) -> dict:
    """Check every registered adapter and return a status report."""
    classes = get_adapter_classes()
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(classes) or 1)) as ex:
        futures = {}
        for aid, cls in classes.items():
            try:
                inst = cls()
            except Exception as e:
                results[aid] = {"id": aid, "status": "offline", "error": str(e)}
                continue
            futures[ex.submit(inst.health_check)] = aid
        for fut in concurrent.futures.as_completed(futures, timeout=timeout):
            aid = futures[fut]
            try:
                results[aid] = fut.result()
            except Exception as e:
                results[aid] = {"id": aid, "status": "offline", "error": str(e)}

    # Ensure every adapter has an entry (in case a future errored before submit)
    for aid, cls in classes.items():
        if aid not in results:
            results[aid] = {"id": aid, "status": "unknown"}
    return results


def health_report() -> str:
    """Human-readable status table for the GUI/log."""
    report = run_health_check()
    lines = ["Agent health check:"]
    order = ["smolagents", "crewai", "langgraph", "browser-use",
             "cua", "agent-framework", "openhands", "open-browser-use", "mindcraft"]
    for aid in order:
        if aid not in report:
            continue
        r = report[aid]
        status = r.get("status", "unknown")
        lines.append(f"  {aid:<20} {status.upper():<9} {r.get('note','')}")
    for aid in report:
        if aid not in order:
            r = report[aid]
            lines.append(f"  {aid:<20} {r.get('status','unknown').upper():<9}")
    return "\n".join(lines)
