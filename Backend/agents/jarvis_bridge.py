
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from Backend.agents import Router, AgentRegistry, AgentResult
from Backend.agents.base import AgentResult as _R
from Backend.agents import status
from Backend.agents.tools import linux_tools, files_tools, media_tools
def _write_response(text):
    rpath = os.path.join(os.getcwd(), "Frontend", "Files", "Response.data")
    try:
        with open(rpath, "w", encoding="utf-8") as f:
            f.write(str(text))
    except Exception:
        pass
def _tool_app(task):
    task = task.lower()
    for word in ("open ", "launch ", "start "):
        if task.startswith(word):
            app = task[len(word):]
            r = linux_tools.open_app(app)
            if r["ok"]:
                return _R(status="success", output=r.get("message"))
            import webbrowser
            sites = {
                "youtube": "https://youtube.com",
                "google": "https://google.com",
                "github": "https://github.com",
                "gmail": "https://gmail.com",
                "maps": "https://maps.google.com",
                "drive": "https://drive.google.com",
                "chatgpt": "https://chatgpt.com",
                "twitter": "https://twitter.com",
                "x": "https://x.com",
                "instagram": "https://instagram.com",
                "facebook": "https://facebook.com",
                "reddit": "https://reddit.com",
                "netflix": "https://netflix.com",
                "spotify": "https://open.spotify.com",
            }
            url = sites.get(app)
            if not url:
                try:
                    from Backend.agents.llm import chat
                    resp = chat([{"role": "user", "content": f"What is the URL for {app}? Reply with ONLY the URL, nothing else."}], max_tokens=100, temperature=0.0)
                    resp = resp.strip().strip('"').strip("'")
                    if resp.startswith("http"):
                        url = resp
                except Exception:
                    pass
            if not url and "." in app and " " not in app:
                url = f"https://{app}" if not app.startswith("http") else app
            if url:
                webbrowser.open(url)
                return _R(status="success", output=f"Opened {app} in browser")
            return _R(status="failed", output=r.get("message"))
    for word in ("close ", "exit ", "kill "):
        if task.startswith(word):
            r = linux_tools.close_app(task[len(word):])
            return _R(status="success" if r["ok"] else "failed", output=r.get("message"))
    if task.startswith("restart "):
        r = linux_tools.restart_app(task[8:])
        return _R(status="success" if r["ok"] else "failed", output=r.get("message"))
    return _R(status="failed", output=f"Unrecognized app action: {task}")
def _tool_media(task):
    task = task.lower()
    for word, fn in (("pause", media_tools.pause), ("resume", media_tools.resume),
                     ("stop", media_tools.stop), ("next", media_tools.next_track),
                     ("previous", media_tools.prev_track), ("prev", media_tools.prev_track)):
        if task.startswith(word):
            r = fn()
            return _R(status="success" if r["ok"] else "failed", output=r.get("message"))
    on_browser = any(kw in task for kw in ["on browser", "on youtube", "on web", "online"])
    query = task.replace("play", "").replace("music", "").replace("some", "").strip()
    if on_browser:
        import webbrowser
        q = query if query else "music"
        webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
        return _R(status="success", output=f"Playing {q} on YouTube")
    r = media_tools.play(query=query or None)
    if r["ok"]:
        return _R(status="success", output=r.get("message"))
    import webbrowser
    q = query if query else "music"
    webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
    return _R(status="success", output=f"Playing {q} on YouTube")
def _tool_search(task):
    import webbrowser
    q = task.replace("search", "").replace("google", "").replace("youtube", "")
    q = q.replace("for", "").replace("about", "").strip()
    if "youtube" in task:
        webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
        return _R(status="success", output=f"Searching YouTube for {q}")
    webbrowser.open(f"https://www.google.com/search?q={q}")
    return _R(status="success", output=f"Searching Google for {q}")
def _tool_system(task):
    task = task.lower()
    if task in ("shutdown", "shut down", "restart", "reboot"):
        return _R(status="success", output=f"{task.title()} requires sudo; not executed automatically")
    if "volume" in task:
        import re
        m = re.search(r"(\d+)", task)
        r = linux_tools.set_volume(int(m.group(1))) if m else linux_tools.get_volume()
        return _R(status="success" if r["ok"] else "failed", output=r.get("message", r))
    if "brightness" in task:
        import re
        m = re.search(r"(\d+)", task)
        r = linux_tools.set_brightness(int(m.group(1))) if m else linux_tools.get_brightness()
        return _R(status="success" if r["ok"] else "failed", output=r.get("message", r))
    if "cpu" in task or "ram" in task or "memory" in task:
        return _R(status="success", output=linux_tools.cpu_ram())
    return _R(status="failed", output=f"Unrecognized system action: {task}")
def _tool_monitor(task):
    return _R(status="success", output=linux_tools.full_system_monitor())
def _tool_process(task):
    task = task.lower()
    if task.startswith("kill ") or task.startswith("terminate "):
        name = task.split()[-1]
        return _R(status="success", output=linux_tools.terminate_process(name))
    if task.startswith("find ") or task.startswith("search "):
        name = task.split()[-1]
        return _R(status="success", output=linux_tools.find_process(name))
    return _R(status="success", output=linux_tools.list_processes())
def _tool_files(task):
    low = task.lower()
    if low.startswith("list "):
        return _R(status="success", output=files_tools.list_dir(task[5:]))
    if low.startswith("search ") or low.startswith("find "):
        return _R(status="success", output=files_tools.search_files(task.split()[-1]))
    if low.startswith("size ") or low.startswith("folder size"):
        return _R(status="success", output=files_tools.folder_size(task.split()[-1]))
    if low.startswith("organize "):
        return _R(status="success", output=files_tools.organize_directory(task[9:]))
    if low.startswith("backup "):
        return _R(status="success", output=files_tools.backup_directory(task[7:]))
    if low.startswith("copy "):
        parts = task[5:].split(" to ")
        if len(parts) == 2:
            src, dst = parts[0].strip(), parts[1].strip()
            return _R(status="success", output=files_tools.copy_file(src, dst))
        return _R(status="failed", output="Specify 'copy <src> to <dst>'")
    if low.startswith("move "):
        parts = task[5:].split(" to ")
        if len(parts) == 2:
            src, dst = parts[0].strip(), parts[1].strip()
            return _R(status="success", output=files_tools.move_file(src, dst))
        return _R(status="failed", output="Specify 'move <src> to <dst>'")
    return _R(status="failed", output="File operation requires confirmation; use explicit tool")
def _tool_minecraft(task):
    from Backend.agents.adapters.mindcraft_adapter import MindcraftAdapter
    adapter = MindcraftAdapter()
    health = adapter.health_check()
    if not adapter.available:
        return _R(status="failed", output=f"Mindcraft offline: {health.get('note')}")
    result = adapter.execute(task)
    return _R(status=result.status, output=result.output or result.summary)
def _tool_create_file(task):
    import re
    from Backend.agents.llm import chat
    m = re.search(r"([\w.\-]+\.\w+)\b", task)
    filename = m.group(1) if m else "script.py"
    if "desktop" in task.lower():
        target_dir = os.path.expanduser("~/Desktop")
    elif "downloads" in task.lower():
        target_dir = os.path.expanduser("~/Downloads")
    elif "document" in task.lower():
        target_dir = os.path.expanduser("~/Documents")
    else:
        target_dir = os.getcwd()
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, filename)
    prompt = (
        "Write complete, working Python source code only (no markdown fences, no "
        "explanations) for the following request. Output ONLY the raw file contents:\n\n"
        f"{task}"
    )
    try:
        code = chat([{"role": "user", "content": prompt}], max_tokens=2048, temperature=0.2)
    except Exception as e:
        return _R(status="failed", output=f"Code generation failed: {e}")
    code = code.strip().strip("```").strip()
    if code.startswith("python\n"):
        code = code[len("python\n"):]
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return _R(status="success", output=f"Created {path}")
    except Exception as e:
        return _R(status="failed", output=f"Failed to write {path}: {e}")
def _tool_reminder(task):
    from Backend.Reminders import add_reminder, list_reminders, cancel_reminder
    task_lower = task.lower().strip()
    if any(kw in task_lower for kw in ["list", "show", "my reminders"]):
        return _R(status="success", output=list_reminders())
    if any(kw in task_lower for kw in ["cancel", "delete", "remove"]):
        ok, msg = cancel_reminder(task_lower)
        return _R(status="success" if ok else "failed", output=msg)
    ok, msg = add_reminder(task_lower)
    return _R(status="success" if ok else "failed", output=msg)
_TOOL_HANDLERS = {
    "app_control": _tool_app,
    "media": _tool_media,
    "web_search": _tool_search,
    "linux_system": _tool_system,
    "system_monitor": _tool_monitor,
    "process_manager": _tool_process,
    "file_manager": _tool_files,
    "file_creator": _tool_create_file,
    "minecraft": _tool_minecraft,
    "reminder": _tool_reminder,
}
class JarvisBridge:
    def __init__(self):
        self.registry = AgentRegistry()
        self.router = Router(self.registry, use_llm_classifier=False)
    def _web_search(self, task: str) -> AgentResult:
        adapter = self.registry.get("browser-use")
        if adapter is not None and adapter.available:
            status.running("web_search")
            result = self.router.run_for_specialist("web_search", task)
            status.completed("web_search")
            if result.status == "success" and result.output.strip():
                _write_response(result.output)
                return result
            print(f"  [browser-use] returned failed: {result.errors}", flush=True)
        status.running("web_search")
        result = _tool_search(task)
        status.completed("web_search")
        _write_response(result.output)
        return result
    def _execute_route(self, task: str, route: str) -> AgentResult:
        if route == "web_search":
            return self._web_search(task)
        if route in _TOOL_HANDLERS:
            status.running(route)
            result = _TOOL_HANDLERS[route](task)
            status.completed(route)
            _write_response(result.output)
            return result
        from Backend.agents import workflows
        if hasattr(workflows, route):
            status.running("planner")
            result = getattr(workflows, route)(self.router, task)
            status.completed("planner")
            _write_response(result.summary or result.output)
            return result
        specialist = route
        if specialist in _TOOL_HANDLERS:
            status.running(specialist)
            result = _TOOL_HANDLERS[specialist](task)
            status.completed(specialist)
            _write_response(result.output)
            return result
        status.running(specialist)
        result = self.router.run_for_specialist(specialist, task)
        status.completed(specialist)
        _write_response(result.output)
        return result
    def run(self, task: str) -> AgentResult:
        status.set_task(task)
        try:
            from Backend.agents import classifier
            route = classifier.decide(task)
            if route:
                return self._execute_route(task, route)
            route = classifier.keyword_route(task)
            if route:
                return self._execute_route(task, route)
            specialist = self.router.route(task)["specialist"]
            if specialist in _TOOL_HANDLERS:
                status.running(specialist)
                result = _TOOL_HANDLERS[specialist](task)
                status.completed(specialist)
                _write_response(result.output)
                return result
            status.running(specialist)
            result = self.router.run(task)
            status.completed(specialist)
            _write_response(result.output)
            return result
        finally:
            status.set_task("")   # clear so GUI task panel/state reset
    def health(self) -> dict:
        return self.registry.status()
_bridge = None
def get_bridge() -> JarvisBridge:
    global _bridge
    if _bridge is None:
        _bridge = JarvisBridge()
    return _bridge
def run_task(task: str) -> AgentResult:
    return get_bridge().run(task)