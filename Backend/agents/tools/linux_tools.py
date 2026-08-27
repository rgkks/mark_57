
from __future__ import annotations
import os
import platform
import re
import shutil
import subprocess
from Backend.agents.permissions import (
    check as _perm, EXECUTE_COMMAND, SYSTEM_CONTROL, OPEN_APPLICATION, CLOSE_APPLICATION,
)
SYSTEM = platform.system().lower()
def _run(cmd: list, timeout: int = 20) -> dict:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "rc": proc.returncode}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"command not found: {cmd[0]}", "rc": 127}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"timed out: {cmd[0]}", "rc": 124}
def _candidates(name: str) -> list:
    from Backend.agents.tools.app_registry import load_registry
    reg = load_registry()
    return reg.get(name.lower(), [name.lower()])
def open_app(name: str, confirmed: bool = False) -> dict:
    name = name.lower().strip()
    if not _perm(OPEN_APPLICATION, confirmed):
        return {"ok": False, "message": "Permission required to launch applications"}
    for exe in _candidates(name):
        path = shutil.which(exe)
        if path:
            subprocess.Popen([path])
            return {"ok": True, "message": f"Launched {exe}"}
    return {"ok": False, "message": f"No known launcher for '{name}'"}
def close_app(name: str, confirmed: bool = False) -> dict:
    name = name.lower().strip()
    if not _perm(CLOSE_APPLICATION, confirmed):
        return {"ok": False, "message": "Permission required to close applications"}
    names = _candidates(name) + [name]
    for n in names:
        r = _run(["pkill", "-f", n])
        if r["ok"]:
            return {"ok": True, "message": f"Closed {name}"}
    return {"ok": True, "message": f"Sent close signal for {name}"}
def restart_app(name: str, confirmed: bool = False) -> dict:
    close_app(name, confirmed)
    import time
    time.sleep(1)
    return open_app(name, confirmed)
def app_running(name: str) -> dict:
    name = name.lower().strip()
    r = _run(["pgrep", "-f", name])
    return {"ok": True, "running": r["ok"], "pid": r["stdout"].strip() or None}
def list_apps() -> dict:
    from Backend.agents.tools.app_registry import available_apps
    return {"ok": True, "apps": available_apps()}
def list_processes(limit: int = 30) -> dict:
    r = _run(["ps", "-eo", "pid,pcpu,pmem,comm", "--sort=-pcpu"])
    lines = r["stdout"].strip().splitlines()
    rows = [lines[0]] + lines[1 : limit + 1]
    return {"ok": True, "processes": rows}
def find_process(name: str) -> dict:
    r = _run(["pgrep", "-af", name])
    return {"ok": True, "found": r["ok"], "matches": r["stdout"].strip().splitlines()}
def process_cpu_mem(pid: int = None) -> dict:
    if pid:
        r = _run(["ps", "-p", str(pid), "-o", "pid,pcpu,pmem,comm", "--no-headers"])
    else:
        r = _run(["ps", "-eo", "pid,pcpu,pmem,comm", "--sort=-pcpu", "--no-headers"])
    return {"ok": True, "processes": r["stdout"].strip().splitlines()}
def terminate_process(name_or_pid, confirmed: bool = False) -> dict:
    if not _perm(SYSTEM_CONTROL, confirmed):
        return {"ok": False, "message": "Permission required to terminate processes"}
    if str(name_or_pid).isdigit():
        r = _run(["kill", str(name_or_pid)])
    else:
        r = _run(["pkill", "-f", str(name_or_pid)])
    return {"ok": r["ok"], "message": f"Terminated {name_or_pid}"}
def restart_process(name_or_pid, confirmed: bool = False) -> dict:
    terminate_process(name_or_pid, confirmed)
    return {"ok": True, "message": f"Restart signal sent for {name_or_pid}"}
def system_info() -> dict:
    info = {
        "os": platform.system(),
        "release": platform.release(),
        "hostname": platform.node(),
        "arch": platform.machine(),
    }
    if os.path.exists("/etc/os-release"):
        for line in open("/etc/os-release", encoding="utf-8"):
            if line.startswith("PRETTY_NAME="):
                info["distro"] = line.split("=", 1)[1].strip().strip('"')
    return {"ok": True, "info": info}
def cpu_ram() -> dict:
    cpu = _run(["bash", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"])
    mem = _run(["bash", "-c", "free -h | awk 'NR==2 {print $3\"/\"$2}'"])
    return {
        "ok": True,
        "cpu_percent": cpu.get("stdout", "").strip(),
        "memory": mem.get("stdout", "").strip(),
    }
def disk_usage() -> dict:
    r = _run(["df", "-h", "--output=source,size,used,avail,pcent", "/"])
    return {"ok": True, "disk": r["stdout"].strip().splitlines()}
def gpu_info() -> dict:
    r = _run(["bash", "-c", "lspci 2>/dev/null | grep -iE 'vga|3d|display'"])
    return {"ok": True, "gpu": r["stdout"].strip().splitlines() or ["No GPU detected"]}
def temperature() -> dict:
    r = _run(["bash", "-c", "sensors 2>/dev/null | grep -iE 'temp|Core' | head -8"])
    return {"ok": True, "temp": r["stdout"].strip().splitlines() or ["sensors not available"]}
def battery() -> dict:
    bat = "/sys/class/power_supply"
    out = []
    if os.path.isdir(bat):
        for dev in os.listdir(bat):
            if dev.startswith("BAT"):
                try:
                    cap = int(open(os.path.join(bat, dev, "capacity")).read().strip())
                    status = open(os.path.join(bat, dev, "status")).read().strip()
                    out.append(f"{dev}: {cap}% ({status})")
                except Exception:
                    pass
    return {"ok": True, "battery": out or ["No battery found (likely desktop)"]}
def network_status() -> dict:
    r = _run(["bash", "-c", "nmcli -t -f DEVICE,TYPE,STATE device 2>/dev/null | head -6 || ip -br addr | grep UP"])
    return {"ok": True, "network": r["stdout"].strip().splitlines() or ["network info unavailable"]}
def uptime() -> dict:
    r = _run(["bash", "-c", "uptime -p"])
    return {"ok": True, "uptime": r["stdout"].strip() or "unknown"}
def full_system_monitor() -> dict:
    return {
        "ok": True,
        **cpu_ram(),
        "disk": disk_usage(),
        "gpu": gpu_info(),
        "temp": temperature(),
        "battery": battery(),
        "network": network_status(),
        "uptime": uptime(),
    }
def _sink():
    r = _run(["pactl", "get-default-sink"])
    return r["stdout"].strip() or "@DEFAULT_SINK@"
def volume(level: int = None, direction: str = None, mute: bool = None) -> dict:
    if direction == "up":
        return {"ok": True, **_run(["pactl", "set-sink-volume", _sink(), "+5%"])}
    if direction == "down":
        return {"ok": True, **_run(["pactl", "set-sink-volume", _sink(), "-5%"])}
    if level is not None:
        pct = max(0, min(150, int(level)))
        return {"ok": True, **_run(["pactl", "set-sink-volume", _sink(), f"{pct}%"])}
    if mute is not None:
        return {"ok": True, **_run(["pactl", "set-sink-mute", _sink(), "1" if mute else "0"])}
    r = _run(["pactl", "get-sink-volume", _sink()])
    return {"ok": True, "volume": r["stdout"].strip()}
def get_volume() -> dict:
    r = _run(["pactl", "get-sink-volume", _sink()])
    return {"ok": True, "volume": r["stdout"].strip()}
def set_volume(level: int, confirmed: bool = False) -> dict:
    if not _perm(SYSTEM_CONTROL, confirmed):
        return {"ok": False, "message": "Permission required to change volume"}
    return volume(level=max(0, min(100, int(level))))
def mute(confirmed: bool = False) -> dict:
    return volume(mute=True) if _perm(SYSTEM_CONTROL, confirmed) else {"ok": False, "message": "Permission required"}
def unmute(confirmed: bool = False) -> dict:
    return volume(mute=False) if _perm(SYSTEM_CONTROL, confirmed) else {"ok": False, "message": "Permission required"}
def _brightness_device():
    backlight = "/sys/class/backlight"
    if os.path.isdir(backlight):
        devices = os.listdir(backlight)
        if devices:
            return os.path.join(backlight, devices[0])
    return None
def get_brightness() -> dict:
    base = _brightness_device()
    if not base:
        return {"ok": False, "message": "No backlight device available"}
    try:
        cur = int(open(os.path.join(base, "brightness")).read().strip())
        mx = int(open(os.path.join(base, "max_brightness")).read().strip())
        return {"ok": True, "brightness_percent": round(cur / mx * 100)}
    except (PermissionError, OSError) as e:
        return {"ok": False, "message": str(e)}
def set_brightness(level: int, confirmed: bool = False) -> dict:
    if not _perm(SYSTEM_CONTROL, confirmed):
        return {"ok": False, "message": "Permission required to change brightness"}
    base = _brightness_device()
    if not base:
        return {"ok": False, "message": "No backlight device available"}
    try:
        mx = int(open(os.path.join(base, "max_brightness")).read().strip())
        target = max(0, min(mx, int(mx * int(level) / 100)))
        open(os.path.join(base, "brightness"), "w").write(str(target))
        return {"ok": True, "brightness_percent": int(level)}
    except (PermissionError, OSError) as e:
        return {"ok": False, "message": f"Brightness needs sudo: {e}"}
def brightness_direction(direction: str, confirmed: bool = False) -> dict:
    cur = get_brightness()
    if not cur["ok"]:
        return cur
    delta = 10 if direction == "up" else -10
    return set_brightness(cur["brightness_percent"] + delta, confirmed)
_DANGEROUS = re.compile(r"(\brm\s+-rf\b|\bdd\s+if=|\bmkfs\b|\bshutdown\b|\breboot\b|\bsudo\b|\brm\b.*/\s*$|\bmv\b.*\/(dev|etc|usr|var)\b)", re.I)
def _is_safe_command(cmd: str) -> bool:
    return not _DANGEROUS.search(cmd)
def run_safe_command(command: str, confirmed: bool = False) -> dict:
    if not _perm(EXECUTE_COMMAND, confirmed):
        return {"ok": False, "message": "Permission required to execute commands"}
    if not _is_safe_command(command):
        return {"ok": False, "message": "Command blocked by safety policy"}
    return _run(["bash", "-lc", command])
def open_terminal(command: str = None) -> dict:
    term = shutil.which("gnome-terminal") or shutil.which("xterm")
    if not term:
        return {"ok": False, "message": "No terminal found"}
    if command and not _is_safe_command(command):
        return {"ok": False, "message": "Command not allowed (permission check)"}
    if command and "gnome-terminal" in term:
        subprocess.Popen([term, "--", "bash", "-lc", command])
    else:
        subprocess.Popen([term])
    return {"ok": True, "message": "Terminal opened"}
if __name__ == "__main__":
    import json
    print(json.dumps(full_system_monitor(), indent=2)[:600])