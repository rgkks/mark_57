from __future__ import annotations

import json
import os
import re
import shutil

_CONFIG_PATH = os.path.join(os.getcwd(), "Data", "apps.json")
_CACHE_PATH = os.path.join(os.getcwd(), "Data", "apps_cache.json")

_DEFAULTS = {
    "browser": ["firefox", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave-browser"],
    "tor browser": ["torbrowser-launcher", "tor", "torbrowser", "tor-browser"],
    "tor": ["torbrowser-launcher", "tor", "torbrowser", "tor-browser"],
    "terminal": ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"],
    "file_manager": ["nemo", "nautilus", "thunar"],
    "vs code": ["code", "code-oss", "codium"],
    "vscode": ["code", "code-oss", "codium"],
    "visual studio code": ["code", "code-oss", "codium"],
    "editor": ["code", "gedit", "kate", "xed"],
    "calculator": ["gnome-calculator", "kcalc", "mate-calc"],
    "music": ["spotify", "rhythmbox", "audacious"],
    "video": ["vlc", "mpv", "totem"],
    "steam": ["steam"],
    "gimp": ["gimp"],
    "blender": ["blender"],
    "libreoffice": ["libreoffice"],
    "screenshot": ["gnome-screenshot", "xfce4-screenshooter", "scrot"],
}


def _scan_desktop_files() -> dict:
    """Scan all .desktop files on the system and build a registry."""
    registry = {}
    desktop_dirs = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        os.path.expanduser("~/.local/share/applications"),
        "/var/lib/flatpak/exports/share/applications",
        "/var/lib/snapd/desktop/applications",
    ]
    for d in desktop_dirs:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            if not fname.endswith(".desktop"):
                continue
            path = os.path.join(d, fname)
            try:
                _parse_desktop_file(path, registry)
            except Exception:
                continue
    return registry


def _parse_desktop_file(path: str, registry: dict):
    """Parse a .desktop file and add to registry."""
    name = None
    exec_cmd = None
    no_display = False
    hidden = False
    categories = []

    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("Name=") and name is None:
                name = line[5:].strip()
            elif line.startswith("Exec="):
                exec_cmd = line[5:].strip()
            elif line.startswith("NoDisplay=true"):
                no_display = True
            elif line.startswith("Hidden=true"):
                hidden = True
            elif line.startswith("Categories="):
                categories = line[12:].split(";")

    if no_display or hidden or not name or not exec_cmd:
        return

    exec_cmd = re.sub(r"%[fFuUdDnNickvm]", "", exec_cmd).strip()
    exe = exec_cmd.split()[0] if exec_cmd else None
    if not exe:
        return

    exe_path = shutil.which(exe)
    if not exe_path:
        return

    key = name.lower().strip()
    if key in registry:
        if exe not in registry[key]:
            registry[key].append(exe)
    else:
        registry[key] = [exe]

    short = os.path.basename(exe).lower().replace(".desktop", "")
    if short != key and short not in registry:
        registry[short] = [exe]


def _build_cache() -> dict:
    """Build and cache the full system registry."""
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    system = _scan_desktop_files()
    try:
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(system, f, indent=2)
    except Exception:
        pass
    return system


def _load_cache() -> dict | None:
    """Load cached registry if fresh (< 1 day old)."""
    try:
        if os.path.exists(_CACHE_PATH):
            age = os.time() - os.path.getmtime(_CACHE_PATH) if hasattr(os, "time") else 0
            import time
            age = time.time() - os.path.getmtime(_CACHE_PATH)
            if age < 86400:
                with open(_CACHE_PATH, encoding="utf-8") as f:
                    return json.load(f)
    except Exception:
        pass
    return None


def load_registry(force=False) -> dict:
    """Load registry: user config + defaults + system scan."""
    user = {}
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                user = json.load(f)
    except Exception:
        pass

    if not force:
        cached = _load_cache()
    else:
        cached = None
    if cached is None:
        cached = _build_cache()

    merged = {}
    merged.update(cached)
    merged.update(_DEFAULTS)
    merged.update(user)
    return merged


def resolve(app_name: str) -> str:
    """Return the first available executable for an app name, or None."""
    reg = load_registry()
    candidates = reg.get(app_name.lower(), [app_name.lower()])
    for exe in candidates:
        path = shutil.which(exe)
        if path:
            return path
    return None


def known_apps() -> list:
    return sorted(load_registry().keys())


def available_apps() -> dict:
    """Map app name -> resolved executable for every configured app that exists."""
    out = {}
    for name in load_registry():
        path = resolve(name)
        if path:
            out[name] = path
    return out
