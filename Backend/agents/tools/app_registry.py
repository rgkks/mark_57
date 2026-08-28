"""Application registry/config for JARVIS.

Maps friendly names -> list of possible launch commands. JARVIS picks the
first available command on the system. User-configurable via Data/apps.json.
"""
from __future__ import annotations

import json
import os
import shutil

_DEFAULTS = {
    "browser": ["firefox", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave-browser"],
    "tor browser": ["torbrowser-launcher", "tor", "torbrowser", "tor-browser"],
    "tor": ["torbrowser-launcher", "tor", "torbrowser", "tor-browser"],
    "terminal": ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"],
    "file_manager": ["nemo", "nautilus", "thunar"],
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

_CONFIG_PATH = os.path.join(os.getcwd(), "Data", "apps.json")


def load_registry() -> dict:
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                user = json.load(f)
            merged = {**_DEFAULTS, **user}
            for k, v in user.items():
                if isinstance(v, list):
                    merged[k] = v
            return merged
    except Exception:
        pass
    return dict(_DEFAULTS)


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