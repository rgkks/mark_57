
from __future__ import annotations
import json
import re
from Backend.agents import llm
TOOL_HANDLERS = [
    ("app_control", "open/launch/close/start an application"),
    ("media", "play/pause/control music, songs, video, media"),
    ("web_search", "search the web or a website (google, youtube, amazon) for information/products"),
    ("linux_system", "system control: shutdown, reboot, volume, brightness, display"),
    ("system_monitor", "report cpu/ram/disk/gpu/battery/uptime/network status"),
    ("process_manager", "list/kill/manage running processes"),
    ("file_manager", "operate on LOCAL files and folders on this computer (list, find, copy, rename, delete)"),
    ("file_creator", "create a new code file / script and save it to disk (e.g. create a chatbot.py and save it on the desktop)"),
    ("minecraft", "control or play Minecraft"),
]
WORKFLOWS = [
    ("debugging_loop", "debug, fix errors, exceptions, crashes, or broken code"),
    ("research_workflow", "in-depth research, investigation, or comparison of a topic"),
    ("coding_workflow", "build/create/write/implement a program, app, script, or feature"),
]
SPECIALISTS = [
    "planner", "task_coordinator", "researcher", "browser", "coder",
    "python_coder", "debugger", "tester", "code_reviewer", "desktop",
    "memory", "summarizer", "verifier",
]
ALL_SPECIALISTS = (
    "planner, task_coordinator, researcher, web_search, browser, coder, python_coder, "
    "debugger, tester, code_reviewer, file_manager, linux_system, app_control, "
    "process_manager, system_monitor, media, desktop, memory, summarizer, verifier, "
    "minecraft"
)
def _build_prompt(task: str) -> str:
    lines = []
    lines.append("You are JARVIS's task router. Decide how to handle the user's request.")
    lines.append("Reply with a JSON object only, like: {\"route\": \"<name>\", \"reason\": \"<short reason>\"}")
    lines.append("")
    lines.append("Available routes and their purpose:")
    for name, desc in TOOL_HANDLERS + WORKFLOWS:
        lines.append(f"- {name}: {desc}")
    lines.append(f"- other specialists: {ALL_SPECIALISTS}")
    lines.append("")
    lines.append("Decision rules:")
    lines.append("- If the request asks to create/write/save a new code file or script (e.g. 'create a chatbot.py') -> file_creator.")
    lines.append("- If the request mentions a website, product search, or 'find ... on <site>' -> web_search.")
    lines.append("- If it asks to find/list/copy/delete LOCAL files or folders -> file_manager.")
    lines.append("- If it is about music/media playback -> media.")
    lines.append("- If it opens/closes apps -> app_control.")
    lines.append("- If it asks about system status -> system_monitor.")
    lines.append("- If it manages processes -> process_manager.")
    lines.append("- If it is debugging/coding/research -> the matching workflow.")
    lines.append("- Otherwise pick the closest specialist.")
    lines.append("")
    lines.append(f"User request: {task}")
    return "\n".join(lines)
def _parse(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            name = str(data.get("route", "")).strip().lower()
            if name:
                return name
        except Exception:
            pass
    for token in text.replace("`", "").split():
        candidate = token.strip(",.!?;:")
        if candidate in ALL_SPECIALISTS.split(", "):
            return candidate
    return ""
def decide(task: str, max_retries: int = 3, model: str = None) -> str:
    models = []
    if model:
        models = [model]
    else:
        models = [llm.fast_model(), llm.strong_model()]
    for model_name in models:
        for attempt in range(max_retries + 1):
            try:
                answer = llm.chat(
                    [{"role": "user", "content": _build_prompt(task)}],
                    max_tokens=120,
                    temperature=0.0,
                    model=model_name,
                )
                route = _parse(answer)
                if route:
                    return route
            except Exception as e:
                if attempt >= max_retries:
                    continue  # try next model
                continue
    return ""
_PRE_ROUTE = [
    ("play ", "media"), ("play\t", "media"), ("play some", "media"),
    ("music", "media"), ("song", "media"), ("track", "media"),
    ("pause", "media"), ("resume", "media"), ("next", "media"), ("previous", "media"),
    ("open ", "app_control"), ("launch ", "app_control"), ("start ", "app_control"),
    ("close ", "app_control"), ("exit ", "app_control"),
    ("restart ", "app_control"),
    ("google", "web_search"), ("youtube", "web_search"), ("search the web", "web_search"),
    ("shutdown", "linux_system"), ("restart", "linux_system"), ("reboot", "linux_system"),
    ("volume", "linux_system"), ("brightness", "linux_system"),
    ("cpu", "linux_system"), ("ram", "linux_system"), ("memory", "linux_system"),
    ("monitor", "system_monitor"), ("system status", "system_monitor"),
    ("disk usage", "system_monitor"), ("gpu", "system_monitor"), ("battery", "system_monitor"),
    ("uptime", "system_monitor"), ("network status", "system_monitor"),
    ("process", "process_manager"), ("task manager", "process_manager"), ("top", "process_manager"),
    ("kill ", "process_manager"), ("terminate ", "process_manager"), ("find process", "process_manager"),
    ("list ", "file_manager"), ("ls ", "file_manager"), ("show files", "file_manager"),
    ("find ", "file_manager"), ("folder size", "file_manager"), ("list files", "file_manager"),
    ("minecraft", "minecraft"),
]
_WORKFLOWS = [
    ("debug", "debugging_loop"), ("fix error", "debugging_loop"), ("crash", "debugging_loop"),
    ("traceback", "debugging_loop"), ("exception", "debugging_loop"), ("bug", "debugging_loop"),
    ("not working", "debugging_loop"), ("broken", "debugging_loop"),
    ("error", "debugging_loop"),
    ("research", "research_workflow"), ("compare", "research_workflow"),
    ("build ", "coding_workflow"), ("create a", "coding_workflow"), ("write a", "coding_workflow"),
    ("make a", "coding_workflow"), ("implement", "coding_workflow"),
]
_WEB_INTENT = ("amazon", "ebay", "alibaba", "flipkart", "best buy", "price", "buy ",
               "on google", "on youtube", "on the web", "shop online", "order", "review", "for sale")
def keyword_route(task: str) -> str:
    low = task.lower().lstrip()
    import re
    if (low.startswith(("create ", "write ", "make ", "save ", "build ")) and
            re.search(r"[\w.\-]+\.\w+", task)):
        return "file_creator"
    if low.startswith(("find ", "search ")) and any(kw in low for kw in _WEB_INTENT):
        return "web_search"
    for prefix, spec in _PRE_ROUTE:
        if low.startswith(prefix):
            return spec
    for kw, wf in _WORKFLOWS:
        if kw in low:
            return wf
    return ""
