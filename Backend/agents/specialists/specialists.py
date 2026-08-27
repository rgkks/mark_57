"""JARVIS specialist agents (20).

Specialists are lightweight routing definitions that map a job onto a
framework adapter + tool layer. They do NOT each run their own LLM; they
delegate to the underlying adapters.
"""
from __future__ import annotations


class Specialist:
    def __init__(self, name, capabilities, preferred, fallbacks, tools=None):
        self.name = name
        self.capabilities = capabilities
        self.preferred = preferred
        self.fallbacks = fallbacks or []
        self.tools = tools or []

    def to_dict(self):
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "preferred": self.preferred,
            "fallbacks": self.fallbacks,
            "tools": self.tools,
        }


SPECIALISTS = [
    # --- Planning & coordination ---
    Specialist(
        "planner",
        ["plan", "planning", "organize", "multi-step", "strategy", "break down", "steps"],
        "langgraph", ["crewai", "smolagents"],
    ),
    Specialist(
        "task_coordinator",
        ["coordinate", "coordinator", "team", "several agents", "delegate", "orchestrate", "run multiple"],
        "crewai", ["langgraph", "smolagents"],
    ),
    # --- Research & web ---
    Specialist(
        "researcher",
        ["research", "investigate", "find out", "analyze", "compare", "latest info"],
        "crewai", ["langgraph", "smolagents"],
    ),
    Specialist(
        "web_search",
        ["search web", "google", "look up", "find information", "search the web"],
        "browser-use", ["smolagents", "crewai"],
    ),
    Specialist(
        "browser",
        ["browser", "open website", "navigate", "web automation", "download page", "click", "scrape"],
        "browser-use", [],
    ),
    # --- Coding ---
    Specialist(
        "coder",
        ["code", "write code", "program", "script", "function", "app", "build", "implement", "refactor"],
        "smolagents", ["crewai", "langgraph"],
    ),
    Specialist(
        "python_coder",
        ["python", "pandas", "numpy", "script.py", "python program", "python function"],
        "smolagents", ["crewai"],
    ),
    Specialist(
        "debugger",
        ["debug", "fix error", "error", "bug", "traceback", "exception", "crash", "fix this"],
        "smolagents", ["crewai", "langgraph"],
    ),
    Specialist(
        "tester",
        ["test", "test case", "unit test", "verify code", "run tests", "pytest"],
        "smolagents", ["crewai"],
    ),
    Specialist(
        "code_reviewer",
        ["review code", "code review", "review this code", "check code quality"],
        "smolagents", ["crewai", "langgraph"],
    ),
    # --- Files & system ---
    Specialist(
        "file_manager",
        ["file", "folder", "directory", "move file", "copy", "rename", "delete", "find a file", "locate"],
        "smolagents", [],
        tools=["files_tools"],
    ),
    Specialist(
        "linux_system",
        ["system", "process", "cpu", "ram", "disk", "volume", "brightness", "terminal", "command"],
        "smolagents", [],
        tools=["linux_tools"],
    ),
    Specialist(
        "app_control",
        ["open app", "launch", "close app", "application", "open firefox", "start ", "run app"],
        "smolagents", [],
        tools=["linux_tools"],
    ),
    Specialist(
        "process_manager",
        ["process", "kill process", "list processes", "top", "task manager", "running processes"],
        "smolagents", [],
        tools=["linux_tools"],
    ),
    Specialist(
        "system_monitor",
        ["monitor", "cpu usage", "ram usage", "disk usage", "gpu", "temperature", "battery", "uptime", "network", "slow"],
        "smolagents", [],
        tools=["linux_tools"],
    ),
    Specialist(
        "media",
        ["music", "play", "song", "media", "video", "album", "playlist", "track"],
        "smolagents", [],
        tools=["media_tools"],
    ),
    Specialist(
        "desktop",
        ["desktop", "screen", "gui control", "computer use", "wallpaper"],
        "cua", ["linux_system"],
        tools=["linux_tools"],
    ),
    # --- Cognition ---
    Specialist(
        "memory",
        ["remember", "recall", "store", "memory", "forget"],
        "langgraph", ["smolagents"],
    ),
    Specialist(
        "summarizer",
        ["summarize", "summary", "shorten", "condense", "summarise"],
        "smolagents", ["crewai", "langgraph"],
    ),
    Specialist(
        "verifier",
        ["verify", "check", "confirm", "validate", "fact-check", "did it work", "double check"],
        "crewai", ["langgraph", "smolagents"],
    ),
    # --- Gaming / embodied ---
    Specialist(
        "minecraft",
        ["minecraft", "mine craft", "play minecraft", "build in minecraft", "minecraft bot", "mine a block"],
        "mindcraft", [],
    ),
]


def get_specialist(name: str):
    for s in SPECIALISTS:
        if s.name == name:
            return s
    return None


def match_specialists(intent: str) -> list:
    """Return specialists whose capabilities/keywords match the intent."""
    il = intent.lower()
    ranked = []
    for s in SPECIALISTS:
        score = 0
        for cap in s.capabilities:
            if cap in il:
                score += 1
        if score:
            ranked.append((score, s))
    ranked.sort(key=lambda x: -x[0])
    return [s for _, s in ranked]