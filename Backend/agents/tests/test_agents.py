"""Test suite for the JARVIS multi-agent system.

Run: python3 -m Backend.agents.tests.test_agents
"""
from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        FAILURES.append((name, detail))
        print(f"  FAIL  {name}  {detail}")


def test_imports():
    print("== imports ==")
    from Backend.agents import BaseAgent, AgentResult, Router, AgentRegistry, run_health_check
    from Backend.agents.specialists import SPECIALISTS
    check("base import", True)
    check("21 specialists", len(SPECIALISTS) == 21, f"got {len(SPECIALISTS)}")


def test_result_normalization():
    print("== result normalization ==")
    from Backend.agents.base import AgentResult
    r = AgentResult(task_id="t1", agent_id="x", status="success", output="hi")
    d = r.to_dict()
    for key in ["task_id", "agent_id", "status", "output", "artifacts", "errors", "metadata"]:
        check(f"normalized key {key}", key in d)
    check("ok()", r.ok())
    check("failed not ok", AgentResult(status="failed").ok() is False)


def test_health_check():
    print("== health check ==")
    from Backend.agents.health import run_health_check
    h = run_health_check()
    check("smolagents reported", h.get("smolagents") is not None)
    check("crewai reported", h.get("crewai") is not None)
    check("langgraph reported", h.get("langgraph") is not None)
    check("browser-use reported", h.get("browser-use") is not None)
    check("cua reported", h.get("cua") is not None)
    check("agent-framework reported", h.get("agent-framework") is not None)
    check("mindcraft reported", h.get("mindcraft") is not None)


def test_registry():
    print("== registry ==")
    from Backend.agents.router import AgentRegistry
    reg = AgentRegistry()
    check("smolagents instantiated", reg.get("smolagents") is not None)
    check("crewai instantiated", reg.get("crewai") is not None)
    check("langgraph instantiated", reg.get("langgraph") is not None)
    check("browser-use instantiated", reg.get("browser-use") is not None)


def test_routing():
    print("== routing ==")
    from Backend.agents import Router, AgentRegistry
    reg = AgentRegistry()
    r = Router(reg, use_llm_classifier=False)
    cases = [
        ("play believer", "media"),
        ("what is 2+2", "coder"),
        ("plan a multi-step task", "planner"),
        ("verify if 5+5 is 10", "verifier"),
        ("search web for nvidia gpus", "web_search"),
        ("summarize this text", "summarizer"),
    ]
    for task, expect in cases:
        s = r.route(task)["specialist"]
        check(f"route({task!r}) -> {expect}", s == expect, f"got {s}")


def test_fallback_decision():
    print("== fallback decisions ==")
    from Backend.agents import Router, AgentRegistry
    from Backend.agents.health import run_health_check
    health = run_health_check()
    health["browser-use"]["status"] = "offline"
    health["cua"]["status"] = "offline"
    reg = AgentRegistry(health=health)
    r = Router(reg, use_llm_classifier=False)
    check("web_search w/o browser -> smolagents", r._pick_framework("web_search") == "smolagents",
          r._pick_framework("web_search"))
    check("desktop w/o cua -> smolagents", r._pick_framework("desktop") == "smolagents",
          r._pick_framework("desktop"))
    check("planner -> langgraph", r._pick_framework("planner") == "langgraph")
    check("coder -> smolagents", r._pick_framework("coder") == "smolagents")


def test_unavailable_adapter():
    print("== unavailable adapter handling ==")
    from Backend.agents.adapters.cua_adapter import CuaAdapter
    a = CuaAdapter()
    hc = a.health_check()
    check("cua reports offline (no sandbox)", hc["status"] == "offline")
    res = a.execute("click the button")
    check("cua execute returns failed, not crash", res.status == "failed")


def test_adapters_health():
    print("== adapters health status ==")
    from Backend.agents.adapters.smolagents_adapter import SmolagentsAdapter
    from Backend.agents.adapters.crewai_adapter import CrewAIAdapter
    from Backend.agents.adapters.langgraph_adapter import LangGraphAdapter
    from Backend.agents.adapters.browser_use_adapter import BrowserUseAdapter
    from Backend.agents.adapters.agent_framework_adapter import AgentFrameworkAdapter
    for cls in [SmolagentsAdapter, CrewAIAdapter, LangGraphAdapter, BrowserUseAdapter,
                AgentFrameworkAdapter]:
        hc = cls().health_check()
        check(f"{cls.id} health online", hc["status"] == "online", hc.get("error"))


def test_linux_tools():
    print("== linux tools ==")
    from Backend.agents.tools import linux_tools
    info = linux_tools.system_info()
    check("system_info ok", info["ok"])
    check("distro detected", bool(info.get("info", {}).get("distro")))
    cr = linux_tools.cpu_ram()
    check("cpu_ram ok", cr["ok"])
    vol = linux_tools.volume(direction="up")
    check("volume up ok", vol["ok"])


def test_files_tools():
    print("== files tools ==")
    from Backend.agents.tools import files_tools
    base = os.getcwd()
    src = os.path.join(base, ".t_src.txt")
    dst = os.path.join(base, ".t_dst.txt")
    files_tools.delete(src, confirm=True)
    files_tools.delete(dst, confirm=True)
    # WRITE_FILES requires confirmation by default -> denied without it
    check("write requires confirm", files_tools.write_file(src, "x")["ok"] is False)
    check("write with confirm", files_tools.write_file(src, "x", confirmed=True)["ok"] is True)
    check("read", files_tools.read_file(src).get("content") == "x")
    check("metadata", files_tools.metadata(src)["size"] == 1)
    check("copy requires confirm", files_tools.copy(src, dst)["ok"] is False)
    check("copy with confirm", files_tools.copy(src, dst, confirmed=True)["ok"] is True)
    check("delete noconfirm blocked", files_tools.delete(dst)["ok"] is False)
    check("delete confirm", files_tools.delete(dst, confirm=True)["ok"] is True)
    files_tools.delete(src, confirm=True)


def test_media_tools():
    print("== media tools ==")
    from Backend.agents.tools import media_tools
    scan = media_tools.scan_music()
    check("media scan returns ok", scan["ok"])


def test_permissions():
    print("== permissions ==")
    from Backend.agents import permissions
    check("safe read allowed", permissions.check(permissions.READ_FILES))
    check("delete requires confirm", permissions.check(permissions.DELETE_FILES) is False)
    check("delete with confirm", permissions.check(permissions.DELETE_FILES, confirmed=True))


def test_app_registry():
    print("== app registry ==")
    from Backend.agents.tools import app_registry
    check("known apps list", len(app_registry.known_apps()) > 5)
    # resolve should find a browser or terminal on a Linux system
    resolved = app_registry.resolve("terminal") or app_registry.resolve("browser")
    check("some app resolves", resolved is not None)


def test_process_monitor():
    print("== process manager ==")
    from Backend.agents.tools import linux_tools
    lp = linux_tools.list_processes()
    check("list processes ok", lp["ok"] and len(lp.get("processes", [])) > 0)
    mon = linux_tools.full_system_monitor()
    check("full monitor ok", mon["ok"])
    check("monitor has cpu_ram", "cpu_percent" in mon)


def test_workflows_routing():
    print("== workflow triggers ==")
    from Backend.agents.classifier import keyword_route
    check("debug -> debugging_loop", keyword_route("fix this python error") == "debugging_loop")
    check("research -> research_workflow", keyword_route("research linux mint") == "research_workflow")
    check("build -> coding_workflow", keyword_route("build a website") == "coding_workflow")


def test_status_tracker():
    print("== status tracker ==")
    from Backend.agents import status
    status.set_task("test task")
    check("task set", status.get_task() == "test task")
    status.running("coder")
    snap = status.snapshot()
    check("snapshot has active task", snap["active_task"] == "test task")
    check("snapshot has agents", isinstance(snap["agents"], list))


def test_mindcraft():
    print("== mindcraft ==")
    from Backend.agents.adapters.mindcraft_adapter import MindcraftAdapter, _port_reachable
    adapter = MindcraftAdapter()
    h = adapter.health_check()
    check("mindcraft health check reports", h.get("status") in ("online", "offline"))
    check("mindcraft installed dir", os.path.isdir(os.path.join(
        os.getcwd(), "Backend", "resources", "agent", "mindcraft")))
    # Without a running Minecraft world, it must be honest and not crash
    r = adapter.execute("build a house")
    check("mindcraft offline execute is failed (no world)", r.status == "failed")
    check("mindcraft port helper works", isinstance(_port_reachable(), bool))


def test_automation_decider():
    print("== automation decider ==")
    from Backend.Model import decide, evaluate
    check("open chrome -> automation", decide("open chrome") == "automation open chrome")
    check("play music -> automation", decide("play some music") == "automation play some music")
    check("volume -> automation", decide("set volume to 30") == "automation set volume to 30")
    check("minecraft -> automation", decide("minecraft build a house") == "automation minecraft build a house")
    check("can you play -> automation", decide("can you play believer").startswith("automation"))
    check("hello -> general", decide("hello") == "general hello")
    check("what is python -> general", decide("what is python") == "general what is python")
    check("stock -> realtime", decide("tata stock price") == "realtime tata stock price")
    check("generate image", decide("generate an image of a dragon") == "generate image of a dragon")
    check("generate video", decide("make an animation") == "generate video animation")
    check("exit -> exit", decide("bye") == "exit")
    check("ambiguous -> None (LLM)", decide("can you help me") is None)
    ev = evaluate()
    check("eval accuracy >= 95", ev["accuracy"] >= 95, f"got {ev['accuracy']}%")


def main():
    tests = [
        test_imports, test_result_normalization, test_health_check, test_registry,
        test_routing, test_fallback_decision, test_unavailable_adapter,
        test_adapters_health, test_linux_tools, test_files_tools, test_media_tools,
        test_permissions, test_app_registry, test_process_monitor,
        test_workflows_routing, test_status_tracker, test_mindcraft,
        test_automation_decider,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            global FAIL
            FAIL += 1
            FAILURES.append((t.__name__, repr(e)))
            print(f"  ERROR {t.__name__}: {e}")
            traceback.print_exc()
    print("\n" + "=" * 40)
    print(f"PASSED: {PASS}   FAILED: {FAIL}")
    if FAILURES:
        print("\nFailures:")
        for name, detail in FAILURES:
            print(f"  - {name}: {detail}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
