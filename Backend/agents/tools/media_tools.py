
from __future__ import annotations
import json
import os
import subprocess
_CONFIG_PATH = os.path.join(os.getcwd(), "Data", "media_config.json")
_DEFAULT_DIRS = [
    os.path.expanduser("~/Music"),
    os.path.expanduser("~/Downloads/Music"),
    os.path.expanduser("~/Music/Music"),
]
_SUPPORTED = (".mp3", ".flac", ".m4a", ".wav", ".ogg", ".opus", ".aac")
PLAYER = None
for _candidate in ["mpv", "vlc", "ffplay"]:
    if subprocess.run(["which", _candidate], capture_output=True).returncode == 0:
        PLAYER = _candidate
        break
def music_dirs() -> list:
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            dirs = cfg.get("music_directories", [])
            if dirs:
                return [os.path.expanduser(d) for d in dirs]
    except Exception:
        pass
    return list(_DEFAULT_DIRS)
def set_music_dirs(dirs: list) -> dict:
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"music_directories": dirs}, f, indent=2)
    return {"ok": True, "configured": dirs}
def scan_music(root: str = None) -> dict:
    roots = [root] if root else music_dirs()
    tracks = []
    for base in roots:
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if fn.lower().endswith(_SUPPORTED):
                    tracks.append(os.path.join(dirpath, fn))
    return {"ok": True, "tracks": tracks, "count": len(tracks)}
def search_music(query: str, root: str = None) -> dict:
    res = scan_music(root)
    if not res["ok"]:
        return res
    q = query.lower()
    matches = [t for t in res["tracks"] if q in os.path.basename(t).lower() or q in t.lower()]
    return {"ok": True, "matches": matches, "count": len(matches)}
def _playerctl(args: list) -> dict:
    if subprocess.run(["which", "playerctl"], capture_output=True).returncode != 0:
        return {"ok": False, "message": "playerctl not installed"}
    r = subprocess.run(["playerctl", *args], capture_output=True, text=True)
    return {"ok": r.returncode == 0, "message": r.stdout.strip() or r.stderr.strip()}
def play(path: str = None, query: str = None) -> dict:
    if query:
        res = search_music(query)
        if res["ok"] and res["matches"]:
            path = res["matches"][0]
        else:
            return {"ok": False, "message": f"No music found for '{query}'"}
    if not PLAYER:
        return {"ok": False, "message": "No media player found"}
    if path and os.path.isfile(path):
        subprocess.Popen([PLAYER, path])
        return {"ok": True, "playing": path}
    return {"ok": False, "message": "No playable path"}
def pause() -> dict:
    return _playerctl(["pause"])
def resume() -> dict:
    return _playerctl(["play"])
def stop() -> dict:
    return _playerctl(["stop"])
def next_track() -> dict:
    return _playerctl(["next"])
def prev_track() -> dict:
    return _playerctl(["previous"])
def media_volume(level: int = None, direction: str = None) -> dict:
    if direction == "up":
        return _playerctl(["volume", "+0.05"])
    if direction == "down":
        return _playerctl(["volume", "-0.05"])
    if level is not None:
        return _playerctl(["volume", str(max(0, min(100, int(level))) / 100)])
    return _playerctl(["volume"])