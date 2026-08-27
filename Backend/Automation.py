
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def log_chat(role, content):
    try:
        path = "Data/Chatlog.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        else:
            history = []
        history.append({"role": role, "content": content})
        if len(history) > 100:
            history = history[-100:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
def _load_agents():
    from Backend.agents.router import AgentRegistry
    registry = AgentRegistry()
    registry._ensure_adapters()
    return registry.adapters
AGENTS = _load_agents()
class _AgentProxy:
    def __init__(self, adapter):
        self._adapter = adapter
    def run(self, task: str):
        from Backend.agents.base import AgentResult
        if self._adapter is None:
            return AgentResult(agent_id="missing", status="failed",
                               errors=["adapter failed to instantiate"])
        return self._adapter.execute(task)
    def health(self):
        return self._adapter.health_check() if self._adapter else {"status": "offline"}
def _make_proxies():
    return {name: _AgentProxy(adapter) for name, adapter in AGENTS.items()}
agents = _make_proxies()
globals().update(agents)
def run_agent(agent_id: str, task: str):
    proxy = agents.get(agent_id)
    if proxy is None:
        raise KeyError(f"unknown agent: {agent_id} (available: {sorted(agents)})")
    return proxy.run(task)
async def Execute(commands):
    from Backend.agents.jarvis_bridge import get_bridge
    bridge = get_bridge()
    tasks = []
    for command in commands:
        command = str(command).strip()
        if not command:
            continue
        query = command[len("automation"):].strip() if command.lower().startswith("automation") else command
        log_chat("user", query)
        tasks.append(asyncio.to_thread(bridge.run, query))
    if tasks:
        results = await asyncio.gather(*tasks)
        for res in results:
            if res and getattr(res, "errors", None):
                print(f"  [Agent] {getattr(res, 'agent_id', '?')} failed: {res.errors}", flush=True)
    return True
Automation = Execute
if __name__ == "__main__":
    while True:
        q = input("Command: ")
        if not q.strip():
            continue
        asyncio.run(Execute([q]))