"""JARVIS permission system.

Explicit permission tokens gate dangerous operations. Policies are
configurable; by default destructive operations require confirmation.
"""
from __future__ import annotations

import json
import os

# Permission tokens
READ_FILES = "READ_FILES"
WRITE_FILES = "WRITE_FILES"
MOVE_FILES = "MOVE_FILES"
DELETE_FILES = "DELETE_FILES"
EXECUTE_COMMAND = "EXECUTE_COMMAND"
OPEN_APPLICATION = "OPEN_APPLICATION"
CLOSE_APPLICATION = "CLOSE_APPLICATION"
NETWORK_ACCESS = "NETWORK_ACCESS"
BROWSER_ACCESS = "BROWSER_ACCESS"
SYSTEM_CONTROL = "SYSTEM_CONTROL"

_ALL = [
    READ_FILES, WRITE_FILES, MOVE_FILES, DELETE_FILES, EXECUTE_COMMAND,
    OPEN_APPLICATION, CLOSE_APPLICATION, NETWORK_ACCESS, BROWSER_ACCESS,
    SYSTEM_CONTROL,
]

# Dangerous permissions: denied by default unless configured allow-all or confirmed.
_SAFE = {READ_FILES, OPEN_APPLICATION, CLOSE_APPLICATION, NETWORK_ACCESS}
# Require explicit confirmation by default.
_REQUIRE_CONFIRM = {DELETE_FILES, MOVE_FILES, WRITE_FILES, EXECUTE_COMMAND, SYSTEM_CONTROL}

_CONFIG_PATH = os.path.join(os.getcwd(), "Data", "permissions.json")


class PermissionPolicy:
    def __init__(self, allow_all: bool = False, allow: set = None, confirm: set = None):
        self.allow_all = allow_all
        self.allow = set(allow or set())
        self.confirm = set(confirm or _REQUIRE_CONFIRM)

    @classmethod
    def load(cls):
        try:
            if os.path.exists(_CONFIG_PATH):
                with open(_CONFIG_PATH, encoding="utf-8") as f:
                    cfg = json.load(f)
                return cls(
                    allow_all=cfg.get("allow_all", False),
                    allow=set(cfg.get("allow", [])),
                    confirm=set(cfg.get("confirm", list(_REQUIRE_CONFIRM))),
                )
        except Exception:
            pass
        return cls()

    def save(self):
        os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "allow_all": self.allow_all,
                "allow": sorted(self.allow),
                "confirm": sorted(self.confirm),
            }, f, indent=2)

    def requires_confirmation(self, token: str) -> bool:
        return token in self.confirm and token not in self.allow and not self.allow_all

    def check(self, token: str, confirmed: bool = False) -> bool:
        """Return True if the permission is granted (or confirmed)."""
        if self.allow_all:
            return True
        if token in self.allow:
            return True
        if token in _SAFE:
            return True
        if token in self.confirm:
            return confirmed
        return False


_default_policy = None


def get_policy() -> PermissionPolicy:
    global _default_policy
    if _default_policy is None:
        _default_policy = PermissionPolicy.load()
    return _default_policy


def check(token: str, confirmed: bool = False) -> bool:
    """Central permission gate used by the tool layer."""
    return get_policy().check(token, confirmed)


def confirm_required(token: str) -> bool:
    return get_policy().requires_confirmation(token)